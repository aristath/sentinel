/**
 * Line-by-Line Diff Utility
 *
 * Provides simple line-by-line diff computation for text comparison.
 * Used primarily for comparing TOML configuration files (e.g., planner config changes).
 *
 * The diff algorithm:
 * - Compares texts line-by-line
 * - Identifies unchanged, added, and removed lines
 * - Uses look-ahead to handle insertions and deletions intelligently
 * - Returns structured diff entries with line numbers
 */

/**
 * Computes a line-by-line diff between two text strings
 *
 * Compares two texts line-by-line and identifies:
 * - Unchanged lines (present in both)
 * - Added lines (only in new text)
 * - Removed lines (only in old text)
 * - Changed lines (different content at same position)
 *
 * Uses a simple look-ahead algorithm to handle insertions and deletions:
 * - Looks ahead up to 3 lines to find matching lines
 * - Treats unmatched lines as additions or deletions
 *
 * @param {string} oldText - Original text
 * @param {string} newText - New text to compare against
 * @returns {Array<Object>} Array of diff entries, each with:
 *   - type: 'unchanged' | 'add' | 'remove'
 *   - content: Line content
 *   - oldLineNum: Line number in old text (null for additions)
 *   - newLineNum: Line number in new text (null for removals)
 */
export function computeLineDiff(oldText, newText) {
  // Split texts into arrays of lines for comparison
  const oldLines = oldText.split('\n');
  const newLines = newText.split('\n');

  const diff = [];
  let oldIndex = 0;  // Current position in old text
  let newIndex = 0;  // Current position in new text

  // Compare lines until both texts are exhausted
  while (oldIndex < oldLines.length || newIndex < newLines.length) {
    // Case 1: Old text exhausted - remaining new lines are additions
    if (oldIndex >= oldLines.length) {
      diff.push({
        type: 'add',
        content: newLines[newIndex],
        oldLineNum: null,
        newLineNum: newIndex + 1,
      });
      newIndex++;
    }
    // Case 2: New text exhausted - remaining old lines are deletions
    else if (newIndex >= newLines.length) {
      diff.push({
        type: 'remove',
        content: oldLines[oldIndex],
        oldLineNum: oldIndex + 1,
        newLineNum: null,
      });
      oldIndex++;
    }
    // Case 3: Lines match - unchanged
    else if (oldLines[oldIndex] === newLines[newIndex]) {
      diff.push({
        type: 'unchanged',
        content: oldLines[oldIndex],
        oldLineNum: oldIndex + 1,
        newLineNum: newIndex + 1,
      });
      oldIndex++;
      newIndex++;
    }
    // Case 4: Lines differ - need to determine if it's addition, deletion, or change
    else {
      // Look ahead in new text to see if current old line appears later
      // This handles insertions (new lines added)
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
        // Look ahead in old text to see if current new line appears later
        // This handles deletions (old lines removed)
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
          // No match found in look-ahead - treat as change: remove old, add new
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
 * Escapes HTML entities in a string to prevent XSS
 *
 * Uses DOM API to safely escape HTML special characters.
 *
 * @param {string} str - String to escape
 * @returns {string} HTML-escaped string
 */
function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

/**
 * Renders a diff as an HTML string for display
 *
 * Creates a visual diff display with:
 * - Context lines around changes (3 lines before/after)
 * - Color-coded additions (green) and removals (red)
 * - Line numbers and change indicators (+/-)
 * - Ellipsis for skipped unchanged sections
 *
 * @param {Array<Object>} diff - Diff entries from computeLineDiff()
 * @param {string} oldLabel - Label for old version (e.g., "Current Config")
 * @param {string} newLabel - Label for new version (e.g., "New Config")
 * @returns {string} HTML string ready for display
 */
export function renderDiffHTML(diff, oldLabel, newLabel) {
  // Find all indices where changes occur (additions or removals)
  const changeIndexes = diff
    .map((entry, index) => entry.type !== 'unchanged' ? index : -1)
    .filter(index => index !== -1);

  // If no changes, show message
  if (changeIndexes.length === 0) {
    return '<div style="padding: 16px; color: var(--mantine-color-dimmed); font-style: italic;">No changes detected</div>';
  }

  // Include context lines around changes for better readability
  const contextLines = 3;  // Show 3 lines before and after each change
  const linesToShow = new Set();

  // For each change, include context lines (unchanged lines around changes)
  changeIndexes.forEach(changeIndex => {
    for (let i = Math.max(0, changeIndex - contextLines);
         i <= Math.min(diff.length - 1, changeIndex + contextLines);
         i++) {
      linesToShow.add(i);
    }
  });

  // Build HTML header with labels
  let html = `
    <div style="margin-bottom: 8px; font-size: 0.875rem; display: flex; justify-content: space-between;">
      <span style="color: var(--mantine-color-red-4);">${escapeHtml(oldLabel)}</span>
      <span style="color: var(--mantine-color-dimmed);">→</span>
      <span style="color: var(--mantine-color-green-4);">${escapeHtml(newLabel)}</span>
    </div>
    <div style="border: 1px solid var(--mantine-color-dark-6); border-radius: 2px; background: var(--mantine-color-dark-8); overflow: auto; max-height: 400px; font-family: var(--mantine-font-family); font-size: 0.875rem;">
  `;

  // Sort line indices and render with context
  const sortedLines = Array.from(linesToShow).sort((a, b) => a - b);
  let lastIndex = -10;  // Track last rendered index to detect gaps

  sortedLines.forEach(index => {
    // If there's a gap between this line and the last, show ellipsis
    if (index - lastIndex > 1) {
      html += '<div style="padding: 4px 8px; color: var(--mantine-color-dimmed); background: var(--mantine-color-dark-7);">...</div>';
    }

    const entry = diff[index];

    // Determine background and text colors based on change type
    const bgColor = entry.type === 'add'
      ? 'var(--mantine-color-green-9)'      // Green background for additions
      : entry.type === 'remove'
      ? 'var(--mantine-color-red-9)'        // Red background for removals
      : 'transparent';                       // Transparent for unchanged

    const textColor = entry.type === 'add'
      ? 'var(--mantine-color-green-0)'      // Light green text for additions
      : entry.type === 'remove'
      ? 'var(--mantine-color-red-0)'         // Light red text for removals
      : 'var(--mantine-color-dark-0)';        // Default text color for unchanged

    // Prefix indicator: + for additions, - for removals, space for unchanged
    const prefix = entry.type === 'add' ? '+' : entry.type === 'remove' ? '-' : ' ';

    // Render line with appropriate styling
    html += `
      <div style="padding: 2px 8px; background: ${bgColor}; color: ${textColor};">
        <span style="margin-right: 8px; color: var(--mantine-color-dimmed);">${prefix}</span>
        <span>${escapeHtml(entry.content || '')}</span>
      </div>
    `;

    lastIndex = index;
  });

  // Add footer with legend
  html += `
    </div>
    <div style="margin-top: 8px; font-size: 0.875rem; color: var(--mantine-color-dimmed);">
      <span style="color: var(--mantine-color-green-4);">+</span> Added
      &nbsp;&nbsp;
      <span style="color: var(--mantine-color-red-4);">-</span> Removed
      &nbsp;&nbsp;
      <span style="color: var(--mantine-color-dark-4);">&nbsp;</span> Unchanged
    </div>
  `;

  return html;
}
