/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#eef1f4",
        card: "#ffffff",
        ink: "#1b2430",
        mist: "#5c6773",
        line: "#d5dbe3",
        teal: "#1e4d78",
        navy: "#1b2430",
        coral: "#9b3a32",
        amber: "#8a5a12",
        sage: "#3f5c4e",
      },
      fontFamily: {
        serif: ["IBM Plex Sans", "ui-sans-serif", "system-ui", "sans-serif"],
        sans: ["IBM Plex Sans", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        card: "none",
      },
    },
  },
  plugins: [],
};
