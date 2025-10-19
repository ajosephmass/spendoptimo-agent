# Web Interface (React Frontend)

This directory contains the SpendOptimo web interface - a conversational UI for interacting with the Analysis Agent.

## Purpose

Provides a user-friendly chat interface for:
- Asking natural language questions about AWS costs
- Viewing optimization recommendations with savings estimates
- Executing workflows with one-click approval
- Tracking execution status and results

## Technology Stack

- **React 18**: UI framework
- **TypeScript**: Type-safe development
- **Vite**: Fast build tool and dev server
- **AWS Amplify**: Authentication with Cognito
- **Markdown Rendering**: Rich formatting for agent responses
- **CSS Modules**: Scoped component styling

## Key Files

### `src/App.tsx`
Main application component:
- Chat interface with message history
- Input field for user queries
- "Execute Recommendations" button
- Session management

### `src/components/ChatMessage.tsx`
Renders individual chat messages:
- User messages (right-aligned)
- Agent responses (left-aligned, markdown-formatted)
- Execution status indicators

### `src/api/agent.ts`
API client for backend communication:
```typescript
// Invoke Analysis Agent
export async function invokeAgent(prompt: string, sessionId: string) {
  const response = await fetch(`${API_URL}/v1/agent/invoke`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${cognitoToken}`
    },
    body: JSON.stringify({ prompt, sessionId })
  });
  return response.json();
}

// Execute optimization workflow
export async function executeWorkflow(recommendations: any[]) {
  const response = await fetch(`${API_URL}/v1/automation`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      action: 'optimize_resources',
      context: { recommendations }
    })
  });
  return response.json();
}
```

### `src/config.ts`
Configuration for API and authentication:
```typescript
export const config = {
  apiUrl: import.meta.env.VITE_API_URL || 'https://api.spendoptimo.com',
  cognitoUserPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID,
  cognitoClientId: import.meta.env.VITE_COGNITO_CLIENT_ID,
  cognitoRegion: import.meta.env.VITE_AWS_REGION || 'us-east-1'
};
```

## Features

### 1. Conversational Interface
Clean chat-style UI similar to ChatGPT:
- User messages on the right
- Agent responses on the left
- Markdown formatting for rich content (tables, lists, code blocks)
- Auto-scroll to latest message

### 2. Authentication
Amazon Cognito integration:
- Sign up / Sign in
- JWT token management
- Automatic token refresh
- Logout functionality

### 3. Recommendation Execution
One-click workflow execution:
- "Execute Recommendations" button appears after agent provides recommendations
- Shows dynamic execution plan
- Displays progress indicator
- Updates status when complete

### 4. Responsive Design
Works across devices:
- Desktop (optimized for wide screens)
- Tablet (collapsible sidebar)
- Mobile (single-column layout)

## Environment Variables

Create `.env` file in `webapp/`:

```bash
VITE_API_URL=https://abc123.execute-api.us-east-1.amazonaws.com/prod
VITE_COGNITO_USER_POOL_ID=us-east-1_ABC123
VITE_COGNITO_CLIENT_ID=abcd1234efgh5678
VITE_AWS_REGION=us-east-1
```

These are injected at build time by Vite.

## Development

### Install Dependencies
```bash
cd webapp
npm install
```

### Run Dev Server
```bash
npm run dev
```

Opens at `http://localhost:5173` with hot reload.

### Build for Production
```bash
npm run build
```

Creates optimized bundle in `dist/`.

### Preview Production Build
```bash
npm run preview
```

## Deployment

Deployed to S3 + CloudFront via CDK:

```bash
# Build UI
cd webapp && npm run build

# Deploy to S3/CloudFront
node deploy-ui.js
```

Or use the full deployment script:
```bash
node deploy-all.js
```

The `deploy-ui.js` script:
1. Builds the React app (`npm run build`)
2. Gets S3 bucket name from CloudFormation
3. Syncs `dist/` to S3
4. Invalidates CloudFront cache
5. Outputs the CloudFront URL

## Project Structure

```
webapp/
├── src/
│   ├── App.tsx                 # Main app component
│   ├── main.tsx                # Entry point
│   ├── api/
│   │   └── agent.ts            # API client
│   ├── components/
│   │   ├── ChatMessage.tsx     # Message rendering
│   │   ├── ChatInput.tsx       # Input field
│   │   └── ExecuteButton.tsx   # Workflow execution button
│   ├── hooks/
│   │   ├── useAuth.ts          # Cognito authentication
│   │   └── useAgent.ts         # Agent invocation
│   ├── config.ts               # Environment config
│   └── styles/
│       └── App.css             # Global styles
├── public/
│   ├── favicon.svg             # App icon
│   └── index.html              # HTML template
├── package.json                # Dependencies
├── vite.config.ts              # Vite configuration
└── tsconfig.json               # TypeScript configuration
```

## Dependencies

### Production
```json
{
  "react": "^18.2.0",
  "react-dom": "^18.2.0",
  "aws-amplify": "^6.0.0",
  "react-markdown": "^9.0.0",
  "axios": "^1.6.0"
}
```

### Development
```json
{
  "vite": "^5.0.0",
  "typescript": "^5.3.0",
  "@vitejs/plugin-react": "^4.2.0",
  "@types/react": "^18.2.0"
}
```

## Customization

### Branding

Edit `src/App.tsx`:
```tsx
<header>
  <h1>YourCompany FinOps</h1>
  <p>AI-powered AWS cost optimization</p>
</header>
```

### Styling

Edit `src/styles/App.css`:
```css
:root {
  --primary-color: #007bff;  /* Your brand color */
  --bg-color: #f8f9fa;
  --text-color: #212529;
}
```

### Example Questions

Update suggested prompts in `src/App.tsx`:
```tsx
const exampleQuestions = [
  "Show me this month's AWS spending",
  "Find cost anomalies in my account",
  "Which Lambda functions are over-provisioned?",
  "Recommend EBS volume optimizations"
];
```

## Sample User Flows

### Flow 1: S3 Optimization
1. User types: "Analyze my S3 buckets for cost optimization"
2. Agent responds with:
   - Total buckets analyzed
   - Policy violations found
   - Estimated savings per bucket
   - Total monthly savings
3. "Execute Recommendations" button appears
4. User clicks button
5. UI shows dynamic execution plan:
   ```
   **Execution Plan:**
   
   **S3 Buckets (8):**
   - Apply Intelligent-Tiering to bucket test-bucket-1
   - Apply Intelligent-Tiering to bucket test-bucket-2
   ...
   
   **Estimated Savings:** $40/month
   
   **Status:** In progress (3-5 minutes)
   ```
6. Workflow executes in background
7. User can continue chatting or wait for completion

### Flow 2: EC2 Rightsizing
1. User types: "Get rightsizing recommendations"
2. Agent responds with:
   - Total EC2 instances analyzed
   - Instances violating policy
   - Recommended instance types
   - Cost savings per instance
3. User clicks "Execute Recommendations"
4. UI shows execution plan:
   ```
   **Execution Plan:**
   
   **EC2 Instances (1):**
   - Stop instance i-abc123
   - Modify from r5.large to t3.medium
   - Restart and verify
   
   **Estimated Savings:** $50/month
   ```
5. Workflow executes: stop → modify → start → verify
6. Agent reports completion

## Performance

### Optimization Techniques
- **Code splitting**: Lazy load components with `React.lazy()`
- **Memoization**: Use `React.memo()` for expensive components
- **Virtual scrolling**: For long message histories
- **Image optimization**: Compress assets, use WebP format
- **CDN caching**: CloudFront serves static assets globally

### Metrics
- **Initial load**: <2 seconds
- **Time to interactive**: <3 seconds
- **Bundle size**: <500KB (gzipped)
- **Lighthouse score**: 95+ (Performance, Accessibility, SEO)

## Security

### Authentication
- Cognito JWT tokens for all API requests
- Tokens stored in memory (not localStorage)
- Automatic refresh before expiration
- Secure logout (invalidate tokens)

### CORS
API Gateway configured to allow requests from CloudFront domain only (in production).

### Content Security Policy
Add CSP headers to prevent XSS:
```html
<meta http-equiv="Content-Security-Policy" 
      content="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';">
```

## Testing

### Unit Tests (Coming Soon)
```bash
npm run test
```

### E2E Tests (Coming Soon)
Using Playwright:
```bash
npm run test:e2e
```

## Troubleshooting

### Issue: "API_URL is undefined"
**Cause:** Missing `.env` file
**Fix:** Create `.env` with `VITE_API_URL=...`

### Issue: CORS errors in browser console
**Cause:** API Gateway not returning CORS headers
**Fix:** Check `api/src/app.py` returns `_cors_headers()`

### Issue: "Unauthorized" errors
**Cause:** Cognito token expired or invalid
**Fix:** Logout and login again to refresh token

### Issue: Build fails with TypeScript errors
**Cause:** Type mismatches
**Fix:** Run `npm run type-check` to see errors, fix them

## Extending the UI

### Adding New Features

Example: Add cost dashboard

1. Create component:
```tsx
// src/components/CostDashboard.tsx
import React from 'react';

export function CostDashboard() {
  const [costs, setCosts] = React.useState([]);
  
  React.useEffect(() => {
    fetch(`${API_URL}/v1/cost-forecast`)
      .then(res => res.json())
      .then(data => setCosts(data.forecast));
  }, []);
  
  return (
    <div className="cost-dashboard">
      <h2>Cost Forecast (30 Days)</h2>
      {/* Render chart */}
    </div>
  );
}
```

2. Import in `App.tsx`:
```tsx
import { CostDashboard } from './components/CostDashboard';

function App() {
  return (
    <>
      <CostDashboard />
      <ChatInterface />
    </>
  );
}
```


