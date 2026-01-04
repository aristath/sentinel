import { Component } from 'react';
import { Alert, Button, Stack, Text } from '@mantine/core';

export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Error caught by boundary:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '2rem', maxWidth: '800px', margin: '0 auto' }}>
          <Alert color="red" title="Something went wrong" variant="filled">
            <Stack gap="md">
              <Text>
                An unexpected error occurred. Please refresh the page or contact support if the problem persists.
              </Text>
              {this.state.error && (
                <details style={{ marginTop: '1rem' }}>
                  <summary style={{ cursor: 'pointer', marginBottom: '0.5rem' }}>
                    Error Details
                  </summary>
                  <pre style={{ 
                    backgroundColor: 'var(--mantine-color-dark-7)', 
                    padding: '1rem', 
                    borderRadius: '4px',
                    overflow: 'auto',
                    fontSize: '12px'
                  }}>
                    {this.state.error.toString()}
                    {this.state.error.stack && `\n${this.state.error.stack}`}
                  </pre>
                </details>
              )}
              <Button
                onClick={() => {
                  this.setState({ hasError: false, error: null });
                  window.location.reload();
                }}
              >
                Reload Page
              </Button>
            </Stack>
          </Alert>
        </div>
      );
    }

    return this.props.children;
  }
}

