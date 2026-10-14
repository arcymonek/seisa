// One rule for every "Clear" button: it is visible only while its tab has something to clear (typed input or a
// result), so the start state shows no Clear at all. A tab supplies `hasContent()` (the rule) and `onClear` (what
// clearing means for that tab); the button is kept in sync here, not by calls scattered through the tab code.
//   inputs: fields whose typing changes the rule ("input" event)
//   watch:  containers whose content, text or `hidden` flag changes the rule (results, status lines, forms); this also
//           covers values set from code (a loaded file, a reopened analysis), which fire no "input" event
// Returns `refresh()` for the rare change that is neither of those.
export function bindClear(button, { hasContent, onClear, inputs = [], watch = [] }) {
  const refresh = () => {
    button.hidden = !hasContent();
  };
  button.addEventListener("click", () => {
    onClear();
    refresh(); // the tab empties its fields from code, which neither fires "input" nor always changes a watched element
  });
  inputs.forEach((el) => el.addEventListener("input", refresh));
  if (watch.length) {
    const observer = new MutationObserver(refresh);
    watch.forEach((el) =>
      observer.observe(el, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ["hidden"] }),
    );
  }
  refresh();
  return refresh;
}
