# Planner Configuration UI - Manual Testing Guide

This document provides a comprehensive manual testing checklist for the planner configuration UI feature.

## Prerequisites

1. Ensure the application is running (`python -m uvicorn app.main:app --reload`)
2. Navigate to the Securities Universe tab
3. Database should be initialized with the latest schema (planner_configs and planner_config_history tables)

## Test Scenarios

### 1. Modal Opening and Closing

**Test: Open the modal**
- [ ] Click "⚙️ Configure Planners" button in Securities Universe tab
- [ ] Modal should appear with:
  - Title "Planner Configuration"
  - Dropdown showing "-- Select a planner --"
  - "+ Add New" button
  - "Close" button in footer
- [ ] No form fields should be visible initially (plannerFormMode = 'none')

**Test: Close the modal**
- [ ] Click the X button in the modal header
- [ ] Modal should close and disappear
- [ ] Click "Configure Planners" again
- [ ] Click the "Close" button in the footer
- [ ] Modal should close

---

### 2. Creating a New Planner Configuration

**Test: Start creating a new planner**
- [ ] Open the modal
- [ ] Click "+ Add New" button
- [ ] Form should appear with:
  - Name field (empty)
  - TOML textarea (with placeholder: "# New planner configuration\n")
  - "Cancel" and "Create Planner" buttons in footer
  - NO "Delete" button

**Test: Create planner with valid TOML**
- [ ] Enter name: "Test Aggressive Growth"
- [ ] Enter valid TOML configuration:
```toml
[planner]
name = "Aggressive Growth"

[[calculators]]
name = "momentum"
type = "momentum"
weight = 1.5

[[calculators]]
name = "growth"
type = "growth"
weight = 1.0
```
- [ ] Click "Create Planner"
- [ ] Success message should appear: "Planner created successfully"
- [ ] Dropdown should now include "Test Aggressive Growth"
- [ ] Form should reset to 'none' mode

**Test: Create planner with invalid TOML**
- [ ] Click "+ Add New"
- [ ] Enter name: "Invalid Test"
- [ ] Enter invalid TOML (missing closing bracket):
```toml
[planner
name = "Invalid"
```
- [ ] Click "Create Planner"
- [ ] Error message should appear in red box: "Invalid TOML syntax"
- [ ] Planner should NOT be created
- [ ] Form should remain in create mode

**Test: Create planner with empty fields**
- [ ] Click "+ Add New"
- [ ] Leave name empty
- [ ] Leave TOML empty
- [ ] "Create Planner" button should be disabled
- [ ] Cannot submit the form

---

### 3. Viewing Existing Planners

**Test: Select a planner from dropdown**
- [ ] Ensure at least one planner exists (create one if needed)
- [ ] Open the modal
- [ ] Select a planner from the dropdown
- [ ] Form should appear with:
  - Name field populated with planner name (editable)
  - TOML textarea populated with planner configuration (monospace font)
  - Bucket ID field (if bucket is assigned, shown as read-only)
  - "Delete", "Cancel", and "Save" buttons in footer
  - Delete button on the left side
  - Cancel and Save on the right side

**Test: Verify TOML formatting**
- [ ] Select a planner with TOML configuration
- [ ] TOML textarea should use monospace font
- [ ] Indentation should be preserved
- [ ] Content should be readable and properly formatted

---

### 4. Updating a Planner Configuration

**Test: Update planner name only**
- [ ] Select a planner from dropdown
- [ ] Change the name to "Updated Name Test"
- [ ] Leave TOML unchanged
- [ ] Click "Save"
- [ ] Success message: "Planner updated successfully"
- [ ] Dropdown should show the new name
- [ ] Planner should still be selected with updated name

**Test: Update TOML configuration only**
- [ ] Select a planner
- [ ] Leave name unchanged
- [ ] Modify the TOML (e.g., change a weight value)
- [ ] Click "Save"
- [ ] Success message: "Planner updated successfully"
- [ ] Select the same planner again
- [ ] TOML changes should be persisted

**Test: Update both name and TOML**
- [ ] Select a planner
- [ ] Change both name and TOML
- [ ] Click "Save"
- [ ] Success message: "Planner updated successfully"
- [ ] Both changes should be persisted

**Test: Update with invalid TOML**
- [ ] Select a planner
- [ ] Break the TOML syntax (e.g., remove a closing bracket)
- [ ] Click "Save"
- [ ] Error message should appear: "Invalid TOML syntax"
- [ ] Changes should NOT be saved
- [ ] Original values should remain in database

**Test: Cancel update**
- [ ] Select a planner
- [ ] Change name and TOML
- [ ] Click "Cancel"
- [ ] Modal should close
- [ ] Re-open modal and select the same planner
- [ ] Changes should NOT be persisted

---

### 5. Deleting a Planner Configuration

**Test: Delete a planner**
- [ ] Create a test planner for deletion
- [ ] Select it from the dropdown
- [ ] Click "Delete" button (should be on the left side)
- [ ] Confirmation dialog should appear: "Are you sure you want to delete this planner configuration?"
- [ ] Click "OK"
- [ ] Success message: "Planner deleted successfully"
- [ ] Planner should be removed from dropdown
- [ ] Form should reset to 'none' mode

**Test: Cancel deletion**
- [ ] Select a planner
- [ ] Click "Delete"
- [ ] Confirmation dialog appears
- [ ] Click "Cancel"
- [ ] Planner should NOT be deleted
- [ ] Planner should still be selected in the form

---

### 6. Loading States

**Test: Loading indicators during fetch**
- [ ] Open the modal
- [ ] Observe spinner during initial planner list fetch
- [ ] Text should show "Loading..."

**Test: Loading during save**
- [ ] Create or edit a planner
- [ ] Click "Save" or "Create Planner"
- [ ] Button should show spinning icon and change text to "Saving..." or "Creating..."
- [ ] Button should be disabled during save

**Test: Loading during delete**
- [ ] Select a planner
- [ ] Click "Delete" and confirm
- [ ] Operations should complete smoothly

---

### 7. Error Handling

**Test: Network error during create**
- [ ] Stop the backend server
- [ ] Try to create a planner
- [ ] Should show error message (may vary based on network error handling)

**Test: Network error during update**
- [ ] Stop the backend server
- [ ] Try to update a planner
- [ ] Should show error message

**Test: Network error during fetch**
- [ ] Stop the backend server
- [ ] Open the modal
- [ ] Should show error message for failed fetch

---

### 8. Version History (Backend Only)

**Test: History is created on update**
- [ ] Create a planner
- [ ] Note the planner ID
- [ ] Update the planner multiple times
- [ ] Check database: `SELECT * FROM planner_config_history WHERE planner_config_id = '<planner-id>'`
- [ ] Should have one history entry for each update
- [ ] History entries should have the old configuration

**Test: History cascade deletion**
- [ ] Create a planner
- [ ] Update it once (creates history)
- [ ] Delete the planner
- [ ] Check database: history entries should also be deleted (CASCADE)

---

### 9. Integration with Bucket System (Future)

**Test: Planner with bucket assignment (when implemented)**
- [ ] Create or select a planner assigned to a bucket
- [ ] Bucket ID field should display the bucket ID (read-only)
- [ ] Note should indicate "Bucket assignments are managed separately"

---

### 10. UI/UX Checks

**Test: Responsive design**
- [ ] Modal should be centered on screen
- [ ] Max width: 4xl
- [ ] Max height: 90vh
- [ ] Content should scroll if needed
- [ ] Modal should work on different screen sizes

**Test: Styling consistency**
- [ ] Modal follows existing design patterns
- [ ] Configure Planners button is green (distinguishes from gray "Manage Universes")
- [ ] Buttons have proper hover states
- [ ] Error messages are styled in red
- [ ] Success messages appear (toast/notification)

**Test: Accessibility**
- [ ] Can navigate with keyboard (Tab, Enter, Esc)
- [ ] Esc key closes the modal
- [ ] Form labels are clear
- [ ] Error messages are visible and associated with fields

---

### 11. Hot-Reload Testing (Backend)

**Test: Hot-reload mechanism (requires bucket)**
- [ ] Assign a planner to a bucket (via database or future UI)
- [ ] Use the planner for trade recommendations
- [ ] Update the planner TOML configuration
- [ ] Use POST `/api/planners/{id}/apply` endpoint
- [ ] Verify planner instance is reloaded without app restart
- [ ] Verify new configuration is used for subsequent recommendations

---

## Expected Results Summary

After completing all tests, the planner configuration UI should:
- ✅ Allow creating new planner configurations with TOML validation
- ✅ Display all existing planners in a dropdown
- ✅ Allow viewing and editing planner configurations
- ✅ Prevent saving invalid TOML configurations
- ✅ Allow deleting planners with confirmation
- ✅ Create version history on every update (backend verification)
- ✅ Show proper loading states during async operations
- ✅ Display clear error messages for validation failures
- ✅ Integrate seamlessly with existing UI design
- ✅ Work correctly across different screen sizes

## Known Limitations

1. **Bucket Assignment UI**: Currently, bucket_id must be assigned via database. UI for bucket assignment will be added in a future iteration.
2. **History Viewing UI**: Version history is stored in the database but there's no UI endpoint to view it yet. Access via GET `/api/planners/{id}/history`.
3. **Apply/Hot-Reload UI**: No UI button to apply a planner. Use POST `/api/planners/{id}/apply` endpoint directly.

## Regression Testing

After testing the planner configuration UI, ensure existing functionality still works:
- [ ] Securities Universe tab loads correctly
- [ ] Other tabs (Next Actions, Diversification, etc.) work normally
- [ ] Manage Universes button still functions
- [ ] No console errors in browser developer tools
- [ ] No layout issues or styling conflicts

---

## Bug Reporting

If you encounter any issues during testing, please report:
1. Test scenario that failed
2. Expected behavior
3. Actual behavior
4. Steps to reproduce
5. Browser console errors (if any)
6. Network tab errors (if any)
