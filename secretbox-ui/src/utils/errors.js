export function authErrorMessage(error) {
  const detail = error.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((issue) => issue.msg).filter((message) => typeof message === 'string').join(' ')
      || 'Please check your username and password.';
  }
  return 'Sign-in is unavailable right now. Please try again later or continue as guest.';
}
