# Changelog - React UI Migration

## [1.0.0] - 2024-01-04

### Added
- Complete React + Vite + Mantine frontend rebuild
- Zustand state management with 6 domain-specific stores
- React Router for navigation with 5 main views
- Mantine component library integration
- Custom chart components (RadarChart, SecurityChart, SecuritySparkline)
- Error boundary for graceful error handling
- Notification system using Mantine notifications
- Test setup with Vitest and React Testing Library
- ESLint configuration
- Comprehensive documentation (README, QUICKSTART, MIGRATION)

### Changed
- Migrated from Alpine.js to React 18
- Replaced Tailwind CSS with Mantine components
- Replaced single Alpine store with Zustand stores
- Converted 27+ JavaScript components to React JSX
- Updated Go server to serve built frontend from `frontend/dist/`
- Updated build script to include frontend build step

### Technical Details
- **Framework**: React 18.2.0
- **Build Tool**: Vite 5.0.0
- **State Management**: Zustand 4.4.0
- **UI Library**: Mantine 7.0.0
- **Routing**: React Router 6.20.0
- **Charts**: Lightweight Charts 4.1.0
- **Testing**: Vitest 1.0.0 + React Testing Library 14.1.0

### Migration Notes
- Old `static/` directory preserved for reference
- Server automatically detects and serves new frontend when built
- All API endpoints remain unchanged
- SSE streams properly integrated with React hooks

