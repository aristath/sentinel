/**
 * Lightweight TOML diff viewer (vanilla JS, no dependencies)
 *
 * Provides simple line-by-line diff comparison between two TOML versions.
 */

/**
 * Compute a simple line-by-line diff between two texts.
 *
 * Uses a basic algorithm that identifies:
 * - Unchanged lines (present in both)
 * - Deleted lines (only in old)
 * - Added lines (only in new)
 *
 * @param {string} oldText - Original text
 * @param {string} newText - New text
 * @returns {Array<Object>} Array of diff entries with type and content
 */
function computeLineDiff(oldText, newText) {
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
        newLineNum: newIndex + 1
      });
      newIndex++;
    } else if (newIndex >= newLines.length) {
      // Remaining lines are all deletions
      diff.push({
        type: 'delete',
        content: oldLines[oldIndex],
        oldLineNum: oldIndex + 1,
        newLineNum: null
      });
      oldIndex++;
    } else if (oldLines[oldIndex] === newLines[newIndex]) {
      // Lines match - unchanged
      diff.push({
        type: 'unchanged',
        content: oldLines[oldIndex],
        oldLineNum: oldIndex + 1,
        newLineNum: newIndex + 1
      });
      oldIndex++;
      newIndex++;
    } else {
      // Lines differ - check if it's a deletion, addition, or change
      // Look ahead to see if we can find a match
      let foundMatch = false;

      // Look ahead in newLines for current oldLine (potential deletion)
      for (let i = newIndex + 1; i < Math.min(newIndex + 5, newLines.length); i++) {
        if (oldLines[oldIndex] === newLines[i]) {
          // Found a match - lines between are additions
          while (newIndex < i) {
            diff.push({
              type: 'add',
              content: newLines[newIndex],
              oldLineNum: null,
              newLineNum: newIndex + 1
            });
            newIndex++;
          }
          foundMatch = true;
          break;
        }
      }

      if (!foundMatch) {
        // Look ahead in oldLines for current newLine (potential addition)
        for (let i = oldIndex + 1; i < Math.min(oldIndex + 5, oldLines.length); i++) {
          if (oldLines[i] === newLines[newIndex]) {
            // Found a match - lines between are deletions
            while (oldIndex < i) {
              diff.push({
                type: 'delete',
                content: oldLines[oldIndex],
                oldLineNum: oldIndex + 1,
                newLineNum: null
              });
              oldIndex++;
            }
            foundMatch = true;
            break;
          }
        }
      }

      if (!foundMatch) {
        // No match found - treat as change (delete + add)
        diff.push({
          type: 'delete',
          content: oldLines[oldIndex],
          oldLineNum: oldIndex + 1,
          newLineNum: null
        });
        diff.push({
          type: 'add',
          content: newLines[newIndex],
          oldLineNum: null,
          newLineNum: newIndex + 1
        });
        oldIndex++;
        newIndex++;
      }
    }
  }

  return diff;
}

/**
 * Render a diff as HTML.
 *
 * @param {Array<Object>} diff - Diff array from computeLineDiff
 * @param {Object} options - Rendering options
 * @returns {string} HTML representation of the diff
 */
function renderDiff(diff, options = {}) {
  const {
    contextLines = 3,  // Show N lines of context around changes
    showAll = false    // Show all lines or only changes with context
  } = options;

  let html = '<div class="diff-viewer font-mono text-xs">';

  // If showing all, just render everything
  if (showAll) {
    diff.forEach(entry => {
      html += renderDiffLine(entry);
    });
  } else {
    // Show only changes with context
    const changeIndexes = diff
      .map((entry, index) => entry.type !== 'unchanged' ? index : -1)
      .filter(index => index !== -1);

    if (changeIndexes.length === 0) {
      html += '<div class="p-4 text-gray-400 italic">No changes detected</div>';
    } else {
      const linesToShow = new Set();

      // For each change, include context lines
      changeIndexes.forEach(changeIndex => {
        for (let i = Math.max(0, changeIndex - contextLines);
             i <= Math.min(diff.length - 1, changeIndex + contextLines);
             i++) {
          linesToShow.add(i);
        }
      });

      // Render lines to show
      const sortedLines = Array.from(linesToShow).sort((a, b) => a - b);
      let lastIndex = -10;

      sortedLines.forEach(index => {
        if (index - lastIndex > 1) {
          // Gap in lines - show ellipsis
          html += '<div class="px-2 py-1 text-gray-500 bg-gray-800/50">...</div>';
        }
        html += renderDiffLine(diff[index]);
        lastIndex = index;
      });
    }
  }

  html += '</div>';
  return html;
}

/**
 * Render a single diff line as HTML.
 *
 * @param {Object} entry - Diff entry with type and content
 * @returns {string} HTML for the line
 */
function renderDiffLine(entry) {
  const escapedContent = (entry.content || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/ /g, '&nbsp;');

  let classes = 'px-2 py-1 whitespace-pre';
  let prefix = '';
  let lineNum = '';

  switch (entry.type) {
    case 'add':
      classes += ' bg-green-900/30 text-green-200';
      prefix = '+&nbsp;';
      lineNum = `<span class="inline-block w-8 text-right text-gray-500">${entry.newLineNum || ''}</span>`;
      break;
    case 'delete':
      classes += ' bg-red-900/30 text-red-200';
      prefix = '-&nbsp;';
      lineNum = `<span class="inline-block w-8 text-right text-gray-500">${entry.oldLineNum || ''}</span>`;
      break;
    case 'unchanged':
      classes += ' text-gray-400';
      prefix = '&nbsp;&nbsp;';
      lineNum = `<span class="inline-block w-8 text-right text-gray-600">${entry.oldLineNum || ''}</span>`;
      break;
  }

  return `<div class="${classes}">${lineNum}&nbsp;${prefix}${escapedContent}</div>`;
}

/**
 * Create a diff comparison modal or panel.
 *
 * @param {string} oldText - Original TOML content
 * @param {string} newText - New TOML content
 * @param {string} oldLabel - Label for old version (e.g., "Version from 2025-01-01")
 * @param {string} newLabel - Label for new version (e.g., "Current version")
 * @returns {string} HTML for diff viewer
 */
function createDiffViewer(oldText, newText, oldLabel = 'Previous', newLabel = 'Current') {
  const diff = computeLineDiff(oldText, newText);
  const diffHtml = renderDiff(diff, { showAll: false, contextLines: 3 });

  return `
    <div class="diff-container">
      <div class="flex items-center justify-between mb-2 text-xs">
        <span class="text-red-300">${escapeHtml(oldLabel)}</span>
        <span class="text-gray-500">→</span>
        <span class="text-green-300">${escapeHtml(newLabel)}</span>
      </div>
      <div class="border border-gray-700 rounded bg-gray-900 overflow-auto max-h-96">
        ${diffHtml}
      </div>
      <div class="mt-2 text-xs text-gray-500">
        <span class="text-green-400">+</span> Added
        &nbsp;&nbsp;
        <span class="text-red-400">-</span> Removed
        &nbsp;&nbsp;
        <span class="text-gray-400">&nbsp;</span> Unchanged
      </div>
    </div>
  `;
}

/**
 * Escape HTML entities.
 *
 * @param {string} str - String to escape
 * @returns {string} Escaped string
 */
function escapeHtml(str) {
  return (str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
