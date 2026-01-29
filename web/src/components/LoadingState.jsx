/**
 * Shared loading state component.
 */
import { Center, Loader } from '@mantine/core';

export default function LoadingState({ message = 'Loading...' }) {
  return (
    <Center h={400}>
      <Loader size="lg" aria-label={message} />
    </Center>
  );
}
