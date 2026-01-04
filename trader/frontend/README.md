# Arduino Trader Frontend

React-based frontend for Arduino Trader portfolio management system.

## Technology Stack

- **React 18** - UI framework
- **Vite** - Build tool and dev server
- **Mantine** - Component library
- **Zustand** - State management
- **React Router** - Routing
- **Vitest** - Testing framework
- **Lightweight Charts** - Charting library

## Development

### Install Dependencies

```bash
npm install
```

### Development Server

```bash
npm run dev
```

The dev server runs on `http://localhost:3000` and proxies API requests to `http://localhost:8080`.

### Build for Production

```bash
npm run build
```

The built files will be in the `dist/` directory, which the Go server will serve.

### Testing

```bash
npm test
```

Run tests in watch mode:

```bash
npm run test:ui
```

## Project Structure

```
frontend/
├── src/
│   ├── components/      # React components
│   │   ├── layout/      # Layout components (Header, StatusBar, etc.)
│   │   ├── portfolio/   # Portfolio-related components
│   │   ├── charts/      # Chart components
│   │   ├── modals/      # Modal components
│   │   └── ...
│   ├── stores/          # Zustand stores
│   ├── api/             # API client
│   ├── hooks/           # Custom React hooks
│   ├── views/           # Route views
│   ├── utils/           # Utility functions
│   └── test/            # Test setup
├── index.html
├── vite.config.js
└── package.json
```

## State Management

State is managed using Zustand stores:

- `appStore` - Application state, modals, loading states
- `portfolioStore` - Portfolio data, allocation, buckets
- `securitiesStore` - Securities list, filters, sorting
- `settingsStore` - Application settings
- `tradesStore` - Recent trades
- `logsStore` - Logs viewer state

## API Integration

All API calls go through the centralized `api` client in `src/api/client.js`. The client handles:
- Request/response formatting
- Error handling
- JSON parsing

## Styling

Uses Mantine components with a dark theme. No Tailwind CSS - all styling is handled by Mantine's component system.

## Deployment

The frontend is built and served by the Go server. The build script (`scripts/build.sh`) will:
1. Build the frontend (`npm run build`)
2. Build the Go binary
3. Serve the frontend from `frontend/dist/`

