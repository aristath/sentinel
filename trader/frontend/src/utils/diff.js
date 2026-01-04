/**
 * Simple line-by-line diff utility for TOML comparison
 */

/**
 * Compute a simple line-by-line diff between two texts
 */
export function computeLineDiff(oldText, newText) {
  const oldLines = oldText.split('\n');
  const newLines = newText.split('\n');

  const diff = [];
  let oldIndex = 0;
  let newIndex = 0;

  while (oldIndex < oldLines.length || newIndex < newLines.length) {
    if (oldIndex >= oldLines.length) {
      // Remaining lines are all additions
      diff.push({
        type: 'add',
        content: newLines[newIndex],
        oldLineNum: null,
        newLineNum: newIndex + 1,
      });
      newIndex++;
    } else if (newIndex >= newLines.length) {
      // Remaining lines are all deletions
      diff.push({
        type: 'remove',
        content: oldLines[oldIndex],
        oldLineNum: oldIndex + 1,
        newLineNum: null,
      });
      oldIndex++;
    } else if (oldLines[oldIndex] === newLines[newIndex]) {
      // Lines match
      diff.push({
        type: 'unchanged',
        content: oldLines[oldIndex],
        oldLineNum: oldIndex + 1,
        newLineNum: newIndex + 1,
      });
      oldIndex++;
      newIndex++;
    } else {
      // Lines differ - check if it's a simple addition/deletion or a change
      // Look ahead to see if we can find a match
      let foundMatch = false;
      for (let lookAhead = 1; lookAhead <= 3 && newIndex + lookAhead < newLines.length; lookAhead++) {
        if (oldLines[oldIndex] === newLines[newIndex + lookAhead]) {
          // Found match ahead - lines in between are additions
          for (let i = 0; i < lookAhead; i++) {
            diff.push({
              type: 'add',
              content: newLines[newIndex + i],
              oldLineNum: null,
              newLineNum: newIndex + i + 1,
            });
          }
          newIndex += lookAhead;
          foundMatch = true;
          break;
        }
      }

      if (!foundMatch) {
        // Check if old line appears later in new text
        let foundOldLater = false;
        for (let lookAhead = 1; lookAhead <= 3 && oldIndex + lookAhead < oldLines.length; lookAhead++) {
          if (oldLines[oldIndex + lookAhead] === newLines[newIndex]) {
            // Old line appears later - current old line is deletion
            diff.push({
              type: 'remove',
              content: oldLines[oldIndex],
              oldLineNum: oldIndex + 1,
              newLineNum: null,
            });
            oldIndex++;
            foundOldLater = true;
            break;
          }
        }

        if (!foundOldLater) {
          // Treat as change: remove old, add new
          diff.push({
            type: 'remove',
            content: oldLines[oldIndex],
            oldLineNum: oldIndex + 1,
            newLineNum: null,
          });
          diff.push({
            type: 'add',
            content: newLines[newIndex],
            oldLineNum: null,
            newLineNum: newIndex + 1,
          });
          oldIndex++;
          newIndex++;
        }
      }
    }
  }

  return diff;
}

/**
 * Escape HTML entities
 */
function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

/**
 * Render diff as HTML string
 */
export function renderDiffHTML(diff, oldLabel, newLabel) {
  const changeIndexes = diff
    .map((entry, index) => entry.type !== 'unchanged' ? index : -1)
    .filter(index => index !== -1);

  if (changeIndexes.length === 0) {
    return '<div style="padding: 16px; color: var(--mantine-color-dimmed); font-style: italic;">No changes detected</div>';
  }

  const contextLines = 3;
  const linesToShow = new Set();

  // For each change, include context lines
  changeIndexes.forEach(changeIndex => {
    for (let i = Math.max(0, changeIndex - contextLines);
         i <= Math.min(diff.length - 1, changeIndex + contextLines);
         i++) {
      linesToShow.add(i);
    }
  });

  let html = `
    <div style="margin-bottom: 8px; font-size: 12px; display: flex; justify-content: space-between;">
      <span style="color: var(--mantine-color-red-4);">${escapeHtml(oldLabel)}</span>
      <span style="color: var(--mantine-color-dimmed);">→</span>
      <span style="color: var(--mantine-color-green-4);">${escapeHtml(newLabel)}</span>
    </div>
    <div style="border: 1px solid var(--mantine-color-dark-4); border-radius: 4px; background: var(--mantine-color-dark-8); overflow: auto; max-height: 400px; font-family: monospace; font-size: 12px;">
  `;

  const sortedLines = Array.from(linesToShow).sort((a, b) => a - b);
  let lastIndex = -10;

  sortedLines.forEach(index => {
    if (index - lastIndex > 1) {
      // Gap in lines - show ellipsis
      html += '<div style="padding: 4px 8px; color: var(--mantine-color-dimmed); background: var(--mantine-color-dark-7);">...</div>';
    }

    const entry = diff[index];
    const bgColor = entry.type === 'add'
      ? 'var(--mantine-color-green-9)'
      : entry.type === 'remove'
      ? 'var(--mantine-color-red-9)'
      : 'transparent';

    const textColor = entry.type === 'add'
      ? 'var(--mantine-color-green-1)'
      : entry.type === 'remove'
      ? 'var(--mantine-color-red-1)'
      : 'var(--mantine-color-gray-0)';

    const prefix = entry.type === 'add' ? '+' : entry.type === 'remove' ? '-' : ' ';

    html += `
      <div style="padding: 2px 8px; background: ${bgColor}; color: ${textColor};">
        <span style="margin-right: 8px; color: var(--mantine-color-dimmed);">${prefix}</span>
        <span>${escapeHtml(entry.content || '')}</span>
      </div>
    `;

    lastIndex = index;
  });

  html += `
    </div>
    <div style="margin-top: 8px; font-size: 12px; color: var(--mantine-color-dimmed);">
      <span style="color: var(--mantine-color-green-4);">+</span> Added
      &nbsp;&nbsp;
      <span style="color: var(--mantine-color-red-4);">-</span> Removed
      &nbsp;&nbsp;
      <span style="color: var(--mantine-color-gray-4);">&nbsp;</span> Unchanged
    </div>
  `;

  return html;
}
