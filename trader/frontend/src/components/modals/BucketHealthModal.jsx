import { Modal, Text } from '@mantine/core';
import { useAppStore } from '../../stores/appStore';

export function BucketHealthModal() {
  const { showBucketHealthModal, selectedBucket, closeBucketHealthModal } = useAppStore();

  return (
    <Modal
      opened={showBucketHealthModal}
      onClose={closeBucketHealthModal}
      title={`Bucket Health: ${selectedBucket?.name || 'Unknown'}`}
      size="lg"
    >
      <Text c="dimmed">Bucket Health modal - to be implemented</Text>
    </Modal>
  );
}

