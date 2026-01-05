# Frontend Completion Plan - Sia Dashboard

## Current State Assessment

### ✅ What's Already Done
- React app structure with Vite
- API proxy configuration (`/api` → `http://127.0.0.1:7432`)
- Complete CSS styling (dark theme)
- Basic components: Header, StatsBar, AgentPanel, WorkUnitPanel
- Polling mechanism (2s interval)
- Error banner for connection failures
- Empty states for panels

### ❌ What Needs Fixing/Completing
1. **Syntax Error**: Missing `return` statement in Header component
2. **API Connection**: Need to verify proxy works correctly
3. **Error Handling**: Basic error handling exists but could be improved
4. **Loading States**: Only initial loading, no skeleton screens
5. **Features**: Missing filtering, sorting, detail views
6. **Production Build**: No build/serve configuration
7. **Real-time**: Using polling instead of SSE/WebSocket

---

## Implementation Plan

### Phase 1: Critical Fixes (Must Have)

#### 1.1 Fix Syntax Errors
**File**: `frontend/src/App.jsx`
- Fix missing `return` in Header component (line 71)
- Verify all components return JSX correctly
- Test component rendering

**Estimated Time**: 15 minutes

#### 1.2 Verify API Connection
**Files**: `frontend/vite.config.js`, `frontend/src/App.jsx`
- Test proxy configuration works
- Verify `/api/work-units/state` endpoint is accessible
- Add CORS handling if needed (backend already has CORS middleware)
- Test with daemon running

**Estimated Time**: 30 minutes

#### 1.3 Improve Error Handling
**File**: `frontend/src/App.jsx`
- Add retry logic with exponential backoff
- Distinguish between network errors and API errors
- Show more specific error messages
- Add error recovery (auto-retry after connection loss)

**Estimated Time**: 1 hour

---

### Phase 2: UX Improvements (Should Have)

#### 2.1 Loading States & Skeletons
**File**: `frontend/src/App.jsx`, `frontend/src/index.css`
- Add skeleton screens for initial load
- Show loading indicators during refresh
- Prevent flickering on updates

**Estimated Time**: 1 hour

#### 2.2 Manual Refresh Control
**File**: `frontend/src/App.jsx`
- Add refresh button in header
- Add configurable poll interval (dropdown: 1s, 2s, 5s, 10s, manual)
- Show last update timestamp
- Pause polling when tab is hidden

**Estimated Time**: 1 hour

#### 2.3 Filtering & Sorting
**File**: `frontend/src/App.jsx`
- Add search/filter for work units (by path, type, owner)
- Add filter for agents (main vs subagent)
- Sort work units (by path, owner, queue length)
- Sort agents (by type, registration time)

**Estimated Time**: 2 hours

---

### Phase 3: Enhanced Features (Nice to Have)

#### 3.1 Expandable Detail Views
**File**: `frontend/src/App.jsx`, `frontend/src/index.css`
- Click work unit to expand and show:
  - Full path
  - TTL countdown timer
  - Complete queue with timestamps
  - Claim/release history (if we add it)
- Click agent to show:
  - All owned work units
  - Registration time
  - Last seen timestamp
  - Agent type details

**Estimated Time**: 2-3 hours

#### 3.2 Responsive Design
**File**: `frontend/src/index.css`
- Make grid responsive (stack on mobile)
- Adjust panel widths for tablets
- Touch-friendly buttons
- Mobile navigation

**Estimated Time**: 2 hours

#### 3.3 Work Unit Actions
**File**: `frontend/src/App.jsx`
- Add "View Details" button for work units
- Show "Copy Path" functionality
- Add tooltips with full information
- Highlight recently changed items

**Estimated Time**: 1 hour

---

### Phase 4: Production Readiness (Must Have for Deployment)

#### 4.1 Production Build Configuration
**Files**: `frontend/vite.config.js`, `backend/main.py`
- Configure Vite build output
- Add static file serving to FastAPI backend
- Update `sia start` to serve frontend
- Add build script to package.json

**Estimated Time**: 1-2 hours

#### 4.2 Environment Configuration
**Files**: `frontend/.env.example`, `frontend/src/App.jsx`
- Add environment variable for API URL
- Support different daemon URLs (dev/prod)
- Add `.env` file handling

**Estimated Time**: 30 minutes

#### 4.3 Testing & Validation
- Test with multiple agents
- Test with queued work units
- Test error scenarios (daemon down, network issues)
- Test on different browsers
- Verify production build works

**Estimated Time**: 2 hours

---

### Phase 5: Advanced Features (Future Enhancements)

#### 5.1 Server-Sent Events (SSE) / WebSocket
**Files**: `backend/main.py`, `frontend/src/App.jsx`
- Replace polling with SSE for real-time updates
- Add WebSocket support for bidirectional communication
- Reduce server load and improve responsiveness

**Estimated Time**: 3-4 hours

#### 5.2 Historical View
**File**: `frontend/src/App.jsx`
- Show work unit claim/release history
- Timeline view of agent activity
- Statistics and analytics

**Estimated Time**: 4-5 hours

#### 5.3 Advanced Filtering
- Filter by agent ID
- Filter by work unit type (file/process/directory)
- Filter by status (available/claimed/queued)
- Save filter presets

**Estimated Time**: 2 hours

---

## File Structure Changes

### New Files to Create
```
frontend/
├── src/
│   ├── components/
│   │   ├── Header.jsx
│   │   ├── StatsBar.jsx
│   │   ├── AgentPanel.jsx
│   │   ├── WorkUnitPanel.jsx
│   │   ├── WorkUnitDetail.jsx
│   │   └── AgentDetail.jsx
│   ├── hooks/
│   │   ├── useApi.js
│   │   └── usePolling.js
│   ├── utils/
│   │   ├── api.js
│   │   └── formatters.js
│   └── App.jsx (refactored)
├── .env.example
└── README.md
```

### Files to Modify
- `frontend/src/App.jsx` - Refactor into smaller components
- `frontend/vite.config.js` - Add build configuration
- `frontend/package.json` - Add build scripts
- `backend/main.py` - Add static file serving (optional)

---

## Implementation Order

### Week 1: Critical Fixes
1. Fix syntax errors
2. Verify API connection
3. Improve error handling
4. Add loading states

### Week 2: Core Features
5. Manual refresh control
6. Filtering & sorting
7. Expandable detail views

### Week 3: Polish & Production
8. Responsive design
9. Production build configuration
10. Testing & validation

### Week 4: Advanced (Optional)
11. SSE/WebSocket implementation
12. Historical view
13. Advanced filtering

---

## Success Criteria

### Minimum Viable Product (MVP)
- ✅ App loads without errors
- ✅ Connects to backend API successfully
- ✅ Displays agents and work units
- ✅ Updates every 2 seconds
- ✅ Shows error when daemon is down
- ✅ Can be built and served in production

### Full Feature Set
- ✅ All MVP features
- ✅ Manual refresh and configurable polling
- ✅ Filtering and sorting
- ✅ Expandable detail views
- ✅ Responsive design
- ✅ Production-ready build

### Advanced Features
- ✅ Real-time updates via SSE/WebSocket
- ✅ Historical data and analytics
- ✅ Advanced filtering options

---

## Testing Checklist

- [ ] App starts without errors
- [ ] API connection works (daemon running)
- [ ] API connection fails gracefully (daemon stopped)
- [ ] Polling updates state correctly
- [ ] Manual refresh works
- [ ] Filtering works for work units
- [ ] Sorting works for both panels
- [ ] Detail views expand/collapse
- [ ] Responsive on mobile/tablet
- [ ] Production build works
- [ ] Static files served correctly
- [ ] Works in Chrome, Firefox, Safari

---

## Notes

- Keep the dark theme consistent
- Maintain accessibility (keyboard navigation, screen readers)
- Use React best practices (hooks, proper state management)
- Consider adding React Query or SWR for better data fetching
- Keep bundle size small (current setup is minimal)

