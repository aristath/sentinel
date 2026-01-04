# Quick Start Guide

## First Time Setup

1. **Install dependencies:**
   ```bash
   cd trader/frontend
   npm install
   ```

2. **Start development server:**
   ```bash
   npm run dev
   ```
   The app will be available at `http://localhost:3000`

3. **Make sure the Go backend is running:**
   ```bash
   cd trader
   go run ./cmd/server
   ```
   The backend should be running on `http://localhost:8080`

## Development Workflow

### Running the App
- Frontend dev server: `npm run dev` (port 3000)
- Backend server: `go run ./cmd/server` (port 8080)
- The frontend dev server proxies `/api/*` requests to the backend

### Building for Production
```bash
cd trader/frontend
npm run build
```

The built files will be in `frontend/dist/` and will be automatically served by the Go server.

### Testing
```bash
npm test          # Run tests once
npm run test:ui   # Run tests with UI (watch mode)
```

### Linting
```bash
npm run lint      # Check for issues
npm run lint:fix  # Auto-fix issues
```

## Project Structure

```
frontend/
├── src/
│   ├── components/     # React components
│   │   ├── layout/     # Header, StatusBar, Navigation
│   │   ├── portfolio/  # SecurityTable, NextActionsCard
│   │   ├── charts/     # RadarChart, SecurityChart
│   │   ├── modals/     # All modal components
│   │   ├── trading/    # TradesTable
│   │   └── system/     # LogsViewer
│   ├── stores/         # Zustand state stores
│   ├── api/            # API client
│   ├── hooks/          # Custom React hooks
│   ├── views/          # Route views
│   ├── utils/          # Utility functions
│   └── test/           # Test setup
├── index.html
├── vite.config.js
└── package.json
```

## Key Features

- **State Management**: Zustand stores for app, portfolio, securities, settings, trades, logs
- **Routing**: React Router for tab navigation
- **Charts**: Custom RadarChart and Lightweight Charts integration
- **Real-time Updates**: SSE (Server-Sent Events) for planner status and recommendations
- **Component Library**: Mantine for all UI components
- **Dark Theme**: Built-in dark mode support

## Troubleshooting

### Port Already in Use
If port 3000 is in use, Vite will automatically try the next available port.

### API Connection Issues
- Make sure the Go backend is running on port 8080
- Check that the proxy configuration in `vite.config.js` is correct
- Verify CORS settings in the Go server

### Build Issues
- Clear `node_modules` and reinstall: `rm -rf node_modules && npm install`
- Clear Vite cache: `rm -rf node_modules/.vite`

### Module Not Found
- Run `npm install` to ensure all dependencies are installed
- Check that file paths are correct (case-sensitive on some systems)

## Next Steps

1. Review the component structure in `src/components/`
2. Check the stores in `src/stores/` to understand state management
3. Look at `src/api/client.js` for API integration
4. Read `MIGRATION.md` for details on the migration from Alpine.js

