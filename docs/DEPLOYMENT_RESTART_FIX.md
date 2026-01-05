# Service Restart Fix for NoNewPrivileges

## Problem

The systemd service has `NoNewPrivileges=true` for security, which prevents the deployment system from using `sudo` to restart the service after deployment.

## Solution Implemented

The deployment system now tries multiple methods to restart the service:

1. **Direct systemctl** - May work if polkit allows the user to manage their own services
2. **sudo systemctl** - Traditional method (may fail with NoNewPrivileges)
3. **D-Bus API** - Works without sudo if polkit permissions are configured

If all methods fail, the deployment still succeeds (binary is deployed), but the service restart requires manual intervention.

## Alternative Solutions

If the automatic restart continues to fail, you have these options:

### Option 1: Remove NoNewPrivileges (Simplest)

Edit `/etc/systemd/system/trader.service` and remove or comment out:
```ini
# NoNewPrivileges=true
```

Then reload systemd:
```bash
sudo systemctl daemon-reload
sudo systemctl restart trader
```

**Security Note:** This reduces security isolation but allows automatic restarts.

### Option 2: Configure Polkit Permissions

Create `/etc/polkit-1/rules.d/50-arduino-trader.rules`:
```javascript
polkit.addRule(function(action, subject) {
    if (action.id == "org.freedesktop.systemd1.manage-units" &&
        subject.user == "arduino" &&
        action.lookup("unit") == "trader.service") {
        return polkit.Result.YES;
    }
});
```

This allows the `arduino` user to restart the `trader` service via D-Bus without sudo.

### Option 3: Create Helper Script

Create a helper script with proper permissions:
```bash
#!/bin/bash
# /usr/local/bin/restart-trader.sh
systemctl restart trader
```

Make it executable and ensure it's in the PATH. The deployment system can then call this script instead of systemctl directly.

### Option 4: Manual Restart After Deployment

If automatic restart fails, manually restart after deployment:
```bash
sudo systemctl restart trader
```

The deployment system will log a warning but continue successfully.

## Current Status

The deployment system will try all available methods. If restart fails, check the logs for the specific error and choose the appropriate solution above.
