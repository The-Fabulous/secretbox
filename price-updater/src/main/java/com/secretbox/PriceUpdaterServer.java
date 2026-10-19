package com.secretbox;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class PriceUpdaterServer {
    private static final Pattern PRICE_LINE = Pattern.compile(
        "^(.+?)\\s*[-—–]\\s*([\\d][\\d\\s.,]*)\\s*(?:₸|KZT)?\\s*$",
        Pattern.CASE_INSENSITIVE
    );
    private static final Pattern SIZE = Pattern.compile(
        "(?<!\\d)(\\d+(?:[.,]\\d+)?)\\s*(ml|мл|l|л)(?!\\p{L})",
        Pattern.CASE_INSENSITIVE | Pattern.UNICODE_CASE
    );
    private static final HttpClient HTTP = HttpClient.newBuilder()
        .connectTimeout(Duration.ofSeconds(5))
        .build();

    private PriceUpdaterServer() {}

    public static void main(String[] args) throws IOException {
        int port = Integer.parseInt(System.getenv().getOrDefault("UPDATER_PORT", "8081"));
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", port), 0);
        server.createContext("/health", exchange -> respond(exchange, 200, "{\"status\":\"ok\"}"));
        server.createContext("/api/menus", PriceUpdaterServer::handleMenuUpdate);
        server.start();
        System.out.println("SecretBox Java price updater listening on port " + port);
    }

    private static void handleMenuUpdate(HttpExchange exchange) throws IOException {
        addCorsHeaders(exchange);
        if ("OPTIONS".equalsIgnoreCase(exchange.getRequestMethod())) {
            exchange.sendResponseHeaders(204, -1);
            exchange.close();
            return;
        }
        if (!"PUT".equalsIgnoreCase(exchange.getRequestMethod())) {
            respond(exchange, 405, "{\"detail\":\"Use PUT to update a cafe menu\"}");
            return;
        }

        String[] pathParts = exchange.getRequestURI().getPath().split("/");
        if (pathParts.length != 4 || !pathParts[1].equals("api") || !pathParts[2].equals("menus")
            || !pathParts[3].matches("[A-Za-z0-9_-]+")) {
            respond(exchange, 404, "{\"detail\":\"Cafe not found\"}");
            return;
        }

        String authorization = exchange.getRequestHeaders().getFirst("Authorization");
        if (authorization == null || !authorization.startsWith("Bearer ")) {
            respond(exchange, 401, "{\"detail\":\"Authentication is required\"}");
            return;
        }

        try {
            byte[] body = exchange.getRequestBody().readNBytes(2_000_001);
            if (body.length > 2_000_000) {
                respond(exchange, 413, "{\"detail\":\"Menu file is too large (2 MB maximum)\"}");
                return;
            }
            List<MenuItem> items = parseMenu(new String(body, StandardCharsets.UTF_8));
            String apiUrl = System.getenv().getOrDefault("PYTHON_API_URL", "http://127.0.0.1:8000")
                .replaceAll("/+$", "");
            String shopName = URLEncoder.encode(pathParts[3], StandardCharsets.UTF_8).replace("+", "%20");
            HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(apiUrl + "/menu/" + shopName))
                .timeout(Duration.ofSeconds(15))
                .header("Authorization", authorization)
                .header("Content-Type", "application/json; charset=utf-8")
                .PUT(HttpRequest.BodyPublishers.ofString(toJson(items), StandardCharsets.UTF_8))
                .build();
            HttpResponse<String> response = HTTP.send(
                request,
                HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8)
            );
            respond(exchange, response.statusCode(), response.body());
        } catch (IllegalArgumentException exception) {
            respond(exchange, 400, jsonError(exception.getMessage()));
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            respond(exchange, 503, "{\"detail\":\"Menu update was interrupted\"}");
        } catch (IOException exception) {
            respond(exchange, 502, "{\"detail\":\"Could not save the menu in the Python API\"}");
        } finally {
            exchange.close();
        }
    }

    private static List<MenuItem> parseMenu(String content) {
        List<MenuItem> items = new ArrayList<>();
        String[] lines = content.split("\\R");
        for (int index = 0; index < lines.length; index++) {
            String line = lines[index].trim();
            if (!line.isEmpty() && line.charAt(0) == 0xFEFF) {
                line = line.substring(1).trim();
            }
            if (line.isEmpty()) {
                continue;
            }
            MenuItem item = line.contains("|") ? parseDelimitedLine(line) : parsePriceLine(line);
            if (item == null) {
                throw new IllegalArgumentException("Could not read menu line " + (index + 1));
            }
            items.add(item);
        }
        if (items.isEmpty()) {
            throw new IllegalArgumentException("The menu must contain at least one drink");
        }
        return items;
    }

    private static MenuItem parseDelimitedLine(String line) {
        String[] parts = line.split("\\|", -1);
        if (parts.length != 3) {
            throw new IllegalArgumentException("Use: drink name | size (ml or l) | price");
        }
        String name = parts[0].trim();
        if (name.isEmpty()) {
            throw new IllegalArgumentException("Drink names cannot be empty");
        }
        Integer sizeMl = parseSize(parts[1].trim());
        int price = parseNumber(parts[2]);
        return new MenuItem(name, sizeMl, price);
    }

    private static MenuItem parsePriceLine(String line) {
        Matcher priceMatcher = PRICE_LINE.matcher(line);
        if (!priceMatcher.matches()) {
            throw new IllegalArgumentException("Use: drink name — price, or drink | size | price");
        }
        String name = priceMatcher.group(1).trim();
        Matcher sizeMatcher = SIZE.matcher(name);
        Integer sizeMl = null;
        if (sizeMatcher.find()) {
            sizeMl = sizeInMillilitres(sizeMatcher.group(1), sizeMatcher.group(2));
            name = sizeMatcher.replaceAll("").replaceAll("[-—–,()]\\s*$", "").trim();
        }
        if (name.isEmpty()) {
            throw new IllegalArgumentException("Drink names cannot be empty");
        }
        return new MenuItem(name, sizeMl, parseNumber(priceMatcher.group(2)));
    }

    private static Integer parseSize(String value) {
        if (value.isBlank()) {
            return null;
        }
        Matcher matcher = SIZE.matcher(value);
        if (!matcher.matches()) {
            throw new IllegalArgumentException("Size must include ml or l (for example, 350 ml)");
        }
        return sizeInMillilitres(matcher.group(1), matcher.group(2));
    }

    private static int sizeInMillilitres(String amount, String unit) {
        double value = Double.parseDouble(amount.replace(',', '.'));
        double millilitres = unit.equalsIgnoreCase("l") || unit.equalsIgnoreCase("л")
            ? value * 1000
            : value;
        int result = (int) Math.round(millilitres);
        if (result <= 0 || result > 5000) {
            throw new IllegalArgumentException("Drink size must be between 1 and 5000 ml");
        }
        return result;
    }

    private static int parseNumber(String value) {
        String digits = value.replaceAll("\\D", "");
        try {
            int number = Integer.parseInt(digits);
            if (number <= 0 || number > 1_000_000) {
                throw new IllegalArgumentException("Price must be between 1 and 1000000 ₸");
            }
            return number;
        } catch (NumberFormatException exception) {
            throw new IllegalArgumentException("Price must be a whole number", exception);
        }
    }

    private static String toJson(List<MenuItem> items) {
        StringBuilder json = new StringBuilder("{\"items\":[");
        for (int index = 0; index < items.size(); index++) {
            MenuItem item = items.get(index);
            if (index > 0) {
                json.append(',');
            }
            json.append("{\"name\":\"").append(escapeJson(item.name))
                .append("\",\"size_ml\":")
                .append(item.sizeMl == null ? "null" : item.sizeMl)
                .append(",\"price\":").append(item.price).append('}');
        }
        return json.append("]}").toString();
    }

    private static String escapeJson(String value) {
        StringBuilder escaped = new StringBuilder();
        for (char character : value.toCharArray()) {
            switch (character) {
                case '\\':
                    escaped.append("\\\\");
                    break;
                case '"':
                    escaped.append("\\\"");
                    break;
                case '\b':
                    escaped.append("\\b");
                    break;
                case '\f':
                    escaped.append("\\f");
                    break;
                case '\n':
                    escaped.append("\\n");
                    break;
                case '\r':
                    escaped.append("\\r");
                    break;
                case '\t':
                    escaped.append("\\t");
                    break;
                default:
                    if (character < 0x20) {
                        escaped.append(String.format("\\u%04x", (int) character));
                    } else {
                        escaped.append(character);
                    }
            }
        }
        return escaped.toString();
    }

    private static String jsonError(String detail) {
        return "{\"detail\":\"" + escapeJson(detail) + "\"}";
    }

    private static void addCorsHeaders(HttpExchange exchange) {
        String origin = System.getenv().getOrDefault("FRONTEND_ORIGIN", "http://localhost:5173");
        exchange.getResponseHeaders().set("Access-Control-Allow-Origin", origin);
        exchange.getResponseHeaders().set("Access-Control-Allow-Headers", "Authorization, Content-Type");
        exchange.getResponseHeaders().set("Access-Control-Allow-Methods", "PUT, OPTIONS");
        exchange.getResponseHeaders().set("Vary", "Origin");
    }

    private static void respond(HttpExchange exchange, int status, String body) throws IOException {
        addCorsHeaders(exchange);
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json; charset=utf-8");
        exchange.sendResponseHeaders(status, bytes.length);
        exchange.getResponseBody().write(bytes);
        exchange.close();
    }

    private static final class MenuItem {
        private final String name;
        private final Integer sizeMl;
        private final int price;

        private MenuItem(String name, Integer sizeMl, int price) {
            this.name = name;
            this.sizeMl = sizeMl;
            this.price = price;
        }
    }
}
