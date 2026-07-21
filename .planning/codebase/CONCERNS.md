# Technical Concerns & Future Enhancements

## External Dependencies
1. **Third-Party Uptime Risk**: Reliance on external SVG generators (Heroku typing SVG, Vercel stats API) can cause broken image placeholders if third-party free tier limits or services go down.
2. **Third-Party Privacy/Tracking**: External image endpoints receive profile traffic data.

## Enhancement Opportunities
1. **Self-Contained SVG Generation**: Implement custom SVG generator scripts (such as Python GraphQL script + GitHub Actions) to generate native light/dark SVGs with exact LOC, contribution, and star metrics without external web services.
2. **Light/Dark Mode Support**: Upgrade images to use HTML `<picture>` elements for native dark mode / light mode adaptation.
