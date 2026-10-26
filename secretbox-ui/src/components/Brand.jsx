export default function Brand() {
  return (
    <a className="brand" href={import.meta.env.BASE_URL} aria-label="SecretBox home">
            <span className="brand-mark">S</span>
            <span>secretbox<span className="brand-period">.</span></span>
          </a>
  );
}
