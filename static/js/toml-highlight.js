/**
 * Lightweight TOML syntax highlighter (vanilla JS, no dependencies)
 *
 * Provides basic syntax highlighting for TOML in a textarea by
 * overlaying a styled pre element behind it.
 */

/**
 * Highlight TOML syntax with HTML spans.
 *
 * @param {string} code - Raw TOML code
 * @returns {string} HTML with syntax highlighting
 */
function highlightTOML(code) {
  if (!code) return '';

  // Escape HTML first
  const escaped = code
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Apply syntax highlighting with regex patterns
  let highlighted = escaped;

  // Comments (# ... until end of line)
  highlighted = highlighted.replace(
    /(#[^\n]*)/g,
    '<span class="text-gray-500 italic">$1</span>'
  );

  // Section headers ([section] or [[array]])
  highlighted = highlighted.replace(
    /(\[\[?[^\]]+\]\]?)/g,
    '<span class="text-blue-400 font-semibold">$1</span>'
  );

  // Keys (word before =)
  highlighted = highlighted.replace(
    /^([a-zA-Z_][a-zA-Z0-9_-]*)\s*=/gm,
    '<span class="text-purple-400">$1</span> ='
  );

  // Strings (double quoted)
  highlighted = highlighted.replace(
    /("(?:[^"\\]|\\.)*")/g,
    '<span class="text-green-400">$1</span>'
  );

  // Strings (single quoted)
  highlighted = highlighted.replace(
    /('(?:[^'\\]|\\.)*')/g,
    '<span class="text-green-400">$1</span>'
  );

  // Numbers (integers and floats)
  highlighted = highlighted.replace(
    /\b(\d+\.?\d*)\b/g,
    '<span class="text-yellow-400">$1</span>'
  );

  // Booleans
  highlighted = highlighted.replace(
    /\b(true|false)\b/g,
    '<span class="text-orange-400 font-semibold">$1</span>'
  );

  return highlighted;
}

/**
 * Initialize syntax highlighting for a textarea.
 * Creates a pre element overlay with highlighted syntax.
 *
 * @param {HTMLTextAreaElement} textarea - The textarea to highlight
 * @returns {Object} Cleanup and update functions
 */
function initTOMLHighlighter(textarea) {
  // Create wrapper
  const wrapper = document.createElement('div');
  wrapper.className = 'relative';
  wrapper.style.fontFamily = 'monospace';

  // Create highlighted background
  const pre = document.createElement('pre');
  pre.className = 'absolute inset-0 px-3 py-2 overflow-auto pointer-events-none whitespace-pre-wrap break-words';
  pre.style.fontFamily = 'inherit';
  pre.style.fontSize = 'inherit';
  pre.style.lineHeight = 'inherit';
  pre.style.margin = '0';
  pre.setAttribute('aria-hidden', 'true');

  // Make textarea transparent on top
  textarea.style.position = 'relative';
  textarea.style.background = 'transparent';
  textarea.style.color = 'transparent';
  textarea.style.caretColor = '#e5e7eb'; // gray-200

  // Wrap textarea
  const parent = textarea.parentNode;
  parent.insertBefore(wrapper, textarea);
  wrapper.appendChild(pre);
  wrapper.appendChild(textarea);

  // Update highlight function
  const updateHighlight = () => {
    const highlighted = highlightTOML(textarea.value);
    pre.innerHTML = highlighted || '<br>'; // Ensure pre has content for sizing
  };

  // Sync scrolling
  const syncScroll = () => {
    pre.scrollTop = textarea.scrollTop;
    pre.scrollLeft = textarea.scrollLeft;
  };

  // Attach event listeners
  textarea.addEventListener('input', updateHighlight);
  textarea.addEventListener('scroll', syncScroll);

  // Initial highlight
  updateHighlight();

  // Return cleanup and utility functions
  return {
    update: updateHighlight,
    destroy: () => {
      textarea.removeEventListener('input', updateHighlight);
      textarea.removeEventListener('scroll', syncScroll);
      wrapper.parentNode.insertBefore(textarea, wrapper);
      wrapper.remove();
      textarea.style.position = '';
      textarea.style.background = '';
      textarea.style.color = '';
      textarea.style.caretColor = '';
    }
  };
}
