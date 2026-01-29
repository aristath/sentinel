/**
 * Shared error state component.
 */
import { Card, Text, Button, Stack } from '@mantine/core';

export default function ErrorState({ message = 'An error occurred', onRetry }) {
  return (
    <Card shadow="sm" padding="lg" withBorder>
      <Stack align="center" gap="md">
        <Text c="red">{message}</Text>
        {onRetry && (
          <Button onClick={onRetry} variant="light" size="sm">
            Retry
          </Button>
        )}
      </Stack>
    </Card>
  );
}
