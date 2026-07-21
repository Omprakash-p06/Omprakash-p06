# Testing & Verification

## Verification Strategy
- **GitHub Preview**: Test markdown and HTML layout using GitHub web preview or local Markdown preview tools.
- **Workflow Verification**: Monitor GitHub Actions tab for `.github/workflows/main.yml` execution and verify snake SVG rendering on `output` branch.
- **Asset Rendering**: Ensure all third-party URLs (`skillicons.dev`, `komarev.com`, `github-readme-stats`) return HTTP 200 and render correctly in both Light and Dark GitHub themes.
