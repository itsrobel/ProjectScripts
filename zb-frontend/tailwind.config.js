
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./internal/templates/**/*.templ"],
  plugins: [require("@tailwindcss/typography"), require("daisyui")],
  theme: {
    fontFamily: {
      'excali': ["Excalifont", "sans-serif"],
      'mono': ["SFMono-Regular", 'jetbrains mono', "monospace"],
    },
  },
  daisyui: {
    themes: ["wireframe", "dim"],
    base: true,
    styled: true,
    utils: true,
    prefix: "",
    themeRoot: ":root",
  },
  darkMode: ["selector", '[data-theme="dim"]'],
};
