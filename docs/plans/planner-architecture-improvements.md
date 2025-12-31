# Planner Architecture Improvements

## Overview
Additional architectural enhancements to make the modular planner production-ready, observable, and maintainable.

---

## Category 1: Observability & Monitoring

### 1.1 Structured Event System

**Problem**: Currently no visibility into planner operations in real-time.

**Solution**: Event-driven architecture with structured events.

```python
# domain/events.py
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict

@dataclass
class PlannerEvent:
    """Base class for planner events."""
    timestamp: datetime
    bucket_id: str
    event_type: str
    data: Dict[str, Any]

class PlannerEventEmitter:
    """Emit events during planner operations."""

    def emit(self, event: PlannerEvent):
        """Emit event to subscribers."""
        # Publish to event bus
        pass

# Example events:
# - SequenceGenerationStarted
# - SequenceGenerationCompleted
# - SequenceEvaluationStarted
# - SequenceEvaluationCompleted
# - BestSequenceUpdated
# - PlanningCompleted
# - ModuleLoadFailed
# - ConfigurationChanged
```

**Benefits**:
- Real-time monitoring
- Audit trail
- Integration with external systems
- Debugging and diagnostics

**Implementation**: Phase 5.5 (during planner refactor)

---

### 1.2 Performance Profiling & Metrics

**Problem**: No visibility into which modules are slow or expensive.

**Solution**: Built-in performance tracking per module.

```python
# calculations/base.py
import time
from contextlib import contextmanager

class PerformanceTracker:
    """Track performance metrics for modules."""

    def __init__(self):
        self._metrics = {}

    @contextmanager
    def track(self, module_name: str, operation: str):
        """Context manager to track operation time."""
        start = time.time()
        try:
            yield
        finally:
            elapsed = time.time() - start
            key = f"{module_name}.{operation}"
            if key not in self._metrics:
                self._metrics[key] = []
            self._metrics[key].append(elapsed)

    def get_stats(self) -> Dict[str, Dict[str, float]]:
        """Get performance statistics."""
        stats = {}
        for key, times in self._metrics.items():
            stats[key] = {
                'count': len(times),
                'total': sum(times),
                'mean': sum(times) / len(times),
                'min': min(times),
                'max': max(times),
            }
        return stats

# Usage in planner:
class HolisticPlanner:
    def __init__(self, config):
        self.config = config
        self.perf = PerformanceTracker()

    async def identify_opportunities(self, context):
        opportunities = {}
        for calculator in self.opportunity_calculators:
            with self.perf.track(calculator.name, 'calculate'):
                candidates = await calculator.calculate(context, params)
            opportunities[calculator.name] = candidates
        return opportunities
```

**Metrics to track**:
- Time per calculator
- Time per pattern generator
- Time per sequence evaluation
- Number of sequences generated
- Cache hit/miss rates
- Memory usage

**Output example**:
```
Performance Report (Bucket: core):
  profit_taking.calculate: 23 calls, avg 0.15s, total 3.45s
  combinatorial.generate: 5 calls, avg 2.3s, total 11.5s
  evaluation.evaluate_sequence: 1247 calls, avg 0.08s, total 99.76s
```

**Implementation**: Phase 5.5

---

### 1.3 Structured Logging

**Problem**: Logs are unstructured, hard to query.

**Solution**: Structured logging with context.

```python
# domain/logging.py
import logging
import json
from typing import Any, Dict

class StructuredLogger:
    """Structured logger for planner operations."""

    def __init__(self, bucket_id: str, logger: logging.Logger):
        self.bucket_id = bucket_id
        self.logger = logger

    def log(self, level: str, message: str, **kwargs):
        """Log structured message with context."""
        log_data = {
            'bucket_id': self.bucket_id,
            'message': message,
            **kwargs
        }
        self.logger.log(
            getattr(logging, level.upper()),
            json.dumps(log_data)
        )

    def info(self, message: str, **kwargs):
        self.log('info', message, **kwargs)

    def error(self, message: str, **kwargs):
        self.log('error', message, **kwargs)

# Usage:
logger = StructuredLogger('satellite_a', logging.getLogger(__name__))
logger.info(
    "Opportunities identified",
    calculator='profit_taking',
    count=5,
    elapsed_ms=150
)
```

**Benefits**:
- Queryable logs
- Better debugging
- Integration with log aggregation tools
- Per-bucket filtering

**Implementation**: Phase 5

---

## Category 2: Reliability & Error Handling

### 2.1 Graceful Degradation

**Problem**: If one module fails, entire planning fails.

**Solution**: Continue with available modules, report failures.

```python
# domain/planner.py
class HolisticPlanner:
    async def identify_opportunities(self, context):
        opportunities = {}
        failed_calculators = []

        for calculator in self.opportunity_calculators:
            try:
                candidates = await calculator.calculate(context, params)
                opportunities[calculator.name] = candidates
            except Exception as e:
                self.logger.error(
                    f"Calculator {calculator.name} failed",
                    error=str(e),
                    traceback=traceback.format_exc()
                )
                failed_calculators.append(calculator.name)
                opportunities[calculator.name] = []  # Empty list

        # Emit warning if calculators failed
        if failed_calculators:
            self.emit_event(CalculatorFailureEvent(
                failed=failed_calculators,
                bucket_id=self.bucket_id
            ))

        return opportunities
```

**Benefits**:
- Higher availability
- Partial results better than no results
- Visibility into failures

**Implementation**: Phase 6

---

### 2.2 Circuit Breaker Pattern

**Problem**: Repeatedly trying failing modules wastes time.

**Solution**: Automatically disable failing modules temporarily.

```python
# domain/circuit_breaker.py
from datetime import datetime, timedelta
from typing import Dict

class CircuitBreaker:
    """Circuit breaker for modules."""

    def __init__(self, failure_threshold: int = 3, timeout: timedelta = timedelta(minutes=5)):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self._failures: Dict[str, int] = {}
        self._opened_at: Dict[str, datetime] = {}

    def is_open(self, module_name: str) -> bool:
        """Check if circuit is open (module disabled)."""
        if module_name not in self._opened_at:
            return False

        # Check if timeout expired
        if datetime.now() - self._opened_at[module_name] > self.timeout:
            # Reset circuit
            self._failures[module_name] = 0
            del self._opened_at[module_name]
            return False

        return True

    def record_success(self, module_name: str):
        """Record successful execution."""
        self._failures[module_name] = 0
        if module_name in self._opened_at:
            del self._opened_at[module_name]

    def record_failure(self, module_name: str):
        """Record failure and potentially open circuit."""
        self._failures[module_name] = self._failures.get(module_name, 0) + 1

        if self._failures[module_name] >= self.failure_threshold:
            self._opened_at[module_name] = datetime.now()

# Usage in planner:
class HolisticPlanner:
    def __init__(self, config):
        self.config = config
        self.circuit_breaker = CircuitBreaker()

    async def identify_opportunities(self, context):
        opportunities = {}

        for calculator in self.opportunity_calculators:
            if self.circuit_breaker.is_open(calculator.name):
                self.logger.warning(f"Skipping {calculator.name} (circuit open)")
                continue

            try:
                candidates = await calculator.calculate(context, params)
                opportunities[calculator.name] = candidates
                self.circuit_breaker.record_success(calculator.name)
            except Exception as e:
                self.circuit_breaker.record_failure(calculator.name)
                self.logger.error(f"Calculator {calculator.name} failed: {e}")
```

**Benefits**:
- Prevent cascading failures
- Faster recovery
- Better resource utilization

**Implementation**: Phase 6

---

### 2.3 Health Checks

**Problem**: No way to verify planner health before running.

**Solution**: Health check API endpoint.

```python
# api/health.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/planner/health/{bucket_id}")
async def check_planner_health(bucket_id: str):
    """Check planner health for a bucket."""

    # Load planner config
    planner = create_planner_for_bucket(bucket_id)

    health = {
        'status': 'healthy',
        'modules': {},
        'warnings': [],
        'errors': [],
    }

    # Check each module
    for calc in planner.opportunity_calculators:
        try:
            # Verify module is loadable
            params = calc.default_params()
            health['modules'][calc.name] = {'status': 'ok', 'type': 'calculator'}
        except Exception as e:
            health['modules'][calc.name] = {'status': 'error', 'error': str(e)}
            health['errors'].append(f"Calculator {calc.name}: {e}")
            health['status'] = 'unhealthy'

    # Check configuration validity
    errors = ConfigurationValidator.validate(planner.config)
    if errors:
        health['errors'].extend(errors)
        health['status'] = 'unhealthy'

    warnings = ConfigurationValidator.check_dependencies(planner.config)
    health['warnings'].extend(warnings)

    return health
```

**Implementation**: Phase 7

---

## Category 3: Configuration Management

### 3.1 Configuration Versioning

**Problem**: Can't track when/why configurations changed, can't share configs between buckets.

**Solution**: Separate database for planner configurations with version history.

**Design Rationale**:
- Planner configurations are independent entities (not tied to buckets)
- Buckets reference a configuration (can switch configurations easily)
- Configurations have full version history for rollback
- Can share/template configurations across buckets

```sql
-- Separate database: planner_configurations.db

-- Main configurations table
CREATE TABLE planner_configurations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,  -- Technical identifier for version group (e.g., "momentum_hunter")
    title TEXT NOT NULL,  -- User-friendly display name (e.g., "Momentum Hunter - Aggressive")
    description TEXT,  -- Longer explanation of strategy
    config_toml TEXT NOT NULL,
    version INTEGER NOT NULL,  -- Auto-incremented per configuration name
    is_active BOOLEAN DEFAULT 1,  -- Current active version for this name
    created_at TEXT NOT NULL,
    created_by TEXT DEFAULT 'user',  -- 'user' or 'system'
    parent_version_id INTEGER,  -- Previous version (for history chain)
    FOREIGN KEY (parent_version_id) REFERENCES planner_configurations(id)
);

CREATE INDEX idx_config_name_version
    ON planner_configurations(name, version DESC);
CREATE INDEX idx_config_active
    ON planner_configurations(name, is_active);

-- Bucket → Configuration mapping (in main database)
CREATE TABLE bucket_planner_configs (
    bucket_id TEXT PRIMARY KEY,  -- 'core' or satellite ID
    planner_config_id INTEGER NOT NULL,
    assigned_at TEXT NOT NULL,
    FOREIGN KEY (bucket_id) REFERENCES buckets(id)
);
```

```python
# services/config_manager.py
class ConfigurationManager:
    """Manage planner configuration versions."""

    def __init__(self, config_db_path: str = "planner_configurations.db"):
        self.config_db = aiosqlite.connect(config_db_path)

    async def create_new_version(
        self,
        name: str,
        title: str,
        config_toml: str,
        description: str = None,
        parent_version_id: int = None
    ) -> int:
        """Create new configuration version.

        Args:
            name: Technical identifier for version group (e.g., 'momentum_hunter')
            title: User-friendly display name (e.g., 'Momentum Hunter - Aggressive')
            config_toml: TOML configuration string
            description: Longer explanation of changes/strategy
            parent_version_id: ID of previous version (for history chain)
        """

        # Get next version number for this config name
        result = await self.config_db.fetchone(
            "SELECT MAX(version) FROM planner_configurations WHERE name = ?",
            (name,)
        )
        next_version = (result[0] + 1) if result[0] else 1

        # Mark previous versions as inactive
        await self.config_db.execute(
            "UPDATE planner_configurations SET is_active = 0 WHERE name = ? AND is_active = 1",
            (name,)
        )

        # Insert new version
        cursor = await self.config_db.execute(
            """INSERT INTO planner_configurations
               (name, title, description, config_toml, version, is_active, created_at, parent_version_id)
               VALUES (?, ?, ?, ?, ?, 1, ?, ?)""",
            (name, title, description, config_toml, next_version, datetime.now().isoformat(), parent_version_id)
        )
        await self.config_db.commit()
        return cursor.lastrowid

    async def assign_config_to_bucket(
        self,
        bucket_id: str,
        planner_config_id: int
    ):
        """Assign a configuration version to a bucket."""

        await self.main_db.execute(
            """INSERT OR REPLACE INTO bucket_planner_configs
               (bucket_id, planner_config_id, assigned_at)
               VALUES (?, ?, ?)""",
            (bucket_id, planner_config_id, datetime.now().isoformat())
        )
        await self.main_db.commit()

    async def rollback_to_version(
        self,
        bucket_id: str,
        version: int,
        config_name: str
    ):
        """Rollback a bucket to a previous configuration version."""

        # Get the historical config
        row = await self.config_db.fetchone(
            """SELECT id, config_toml FROM planner_configurations
               WHERE name = ? AND version = ?""",
            (config_name, version)
        )

        if not row:
            raise ValueError(f"Version {version} of '{config_name}' not found")

        config_id, config_toml = row

        # Assign to bucket (or create new version marked as rollback)
        await self.assign_config_to_bucket(bucket_id, config_id)

    async def get_bucket_config(self, bucket_id: str) -> dict:
        """Get current configuration for a bucket."""

        row = await self.main_db.fetchone(
            """SELECT pc.* FROM planner_configurations pc
               JOIN bucket_planner_configs bpc ON pc.id = bpc.planner_config_id
               WHERE bpc.bucket_id = ?""",
            (bucket_id,)
        )

        if not row:
            raise ValueError(f"No configuration assigned to bucket '{bucket_id}'")

        return dict(row)

    async def get_version_history(self, config_name: str) -> list:
        """Get version history for a configuration."""

        rows = await self.config_db.fetchall(
            """SELECT id, version, title, description, created_at, created_by, is_active
               FROM planner_configurations
               WHERE name = ?
               ORDER BY version DESC""",
            (config_name,)
        )

        return [dict(row) for row in rows]
```

**Benefits**:
- Separate database keeps config history isolated
- Configurations are reusable entities (share across buckets)
- Full audit trail with version chains
- Easy rollback by reassigning bucket to previous config
- Compare configurations over time
- Understand performance changes linked to config versions
- Template/clone configurations

**Usage Flow**:
1. User creates/edits TOML config in UI → POST `/configs` (creates v1)
2. System assigns config to bucket → POST `/buckets/core/assign-config`
3. Planner factory reads config via `get_bucket_config('core')`
4. User tweaks config → POST `/configs` (creates v2 of same name)
5. System auto-assigns new version to bucket
6. Performance issues? → POST `/buckets/core/rollback` to v1

**API Endpoints**:
```python
# api/planner_config.py
@router.post("/configs")
async def create_config(
    name: str,
    title: str,
    config_toml: str,
    description: str = None
):
    """Create new configuration or new version of existing."""
    config_id = await config_manager.create_new_version(
        name=name,
        title=title,
        config_toml=config_toml,
        description=description
    )
    return {"config_id": config_id}

@router.post("/buckets/{bucket_id}/assign-config")
async def assign_config(bucket_id: str, config_id: int):
    """Assign configuration to a bucket."""
    await config_manager.assign_config_to_bucket(bucket_id, config_id)
    return {"status": "assigned"}

@router.post("/buckets/{bucket_id}/rollback")
async def rollback_config(
    bucket_id: str,
    config_name: str,
    version: int
):
    """Rollback bucket to previous config version."""
    await config_manager.rollback_to_version(bucket_id, version, config_name)
    return {"status": "rolled_back"}

@router.get("/configs/{name}/history")
async def get_history(name: str):
    """Get version history for a configuration."""
    history = await config_manager.get_version_history(name)
    return {"history": history}

@router.get("/buckets/{bucket_id}/config")
async def get_current_config(bucket_id: str):
    """Get current configuration for bucket."""
    config = await config_manager.get_bucket_config(bucket_id)
    return config
```

**Example Workflow**:
```python
# User creates "Momentum Hunter" config
config_id_v1 = await create_config(
    name="momentum_hunter",  # Technical identifier
    title="Momentum Hunter - Aggressive",  # User-friendly display
    config_toml="[core]\nmax_plan_depth = 3\n...",
    description="Aggressive momentum strategy focusing on short-term gains"
)  # Returns config_id=1, version=1

# Assign to satellite_a
await assign_config("satellite_a", config_id_v1)

# User tweaks parameters → creates v2
config_id_v2 = await create_config(
    name="momentum_hunter",  # Same name = new version of same config
    title="Momentum Hunter - Deeper Search",  # Updated title
    config_toml="[core]\nmax_plan_depth = 5\n...",  # Different params
    description="Increased depth for better coverage of opportunities"
)  # Returns config_id=2, version=2

# Auto-assign latest version to satellite_a
await assign_config("satellite_a", config_id_v2)

# Performance worse? Rollback to v1
await rollback_config("satellite_a", "momentum_hunter", version=1)

# UI can display: "Momentum Hunter - Aggressive (v1)" vs "Momentum Hunter - Deeper Search (v2)"
```

**Migration from Current System**:
```python
# One-time migration script
async def migrate_existing_configs():
    """Migrate satellite configs from settings to planner_configurations.db."""

    # Get all satellites
    satellites = await satellites_repo.get_all()

    for satellite in satellites:
        # Get current config from settings or satellite record
        current_config = satellite.get('config_toml')

        if current_config:
            # Create v1 in new system
            config_id = await config_manager.create_new_version(
                name=f"{satellite['id']}_config",  # Technical name
                title=f"{satellite['name']} Strategy",  # Display name
                config_toml=current_config,
                description="Migrated from legacy system"
            )

            # Link bucket to config
            await config_manager.assign_config_to_bucket(
                satellite['id'],
                config_id
            )

    # Create core config from current settings
    core_config_toml = await build_toml_from_settings()
    config_id = await config_manager.create_new_version(
        name="core_conservative",  # Technical identifier
        title="Core - Conservative Long-Term",  # User-friendly title
        config_toml=core_config_toml,
        description="Migrated core planner settings with all features enabled"
    )
    await config_manager.assign_config_to_bucket("core", config_id)
```

**Implementation**: Phase 7

---

### 3.2 Configuration Diffing

**Problem**: Hard to see what changed between configs.

**Solution**: Built-in diff viewer.

```python
# services/config_differ.py
import difflib
from typing import List, Dict

class ConfigurationDiffer:
    """Compare TOML configurations."""

    def diff(self, config_a: str, config_b: str) -> List[str]:
        """Generate unified diff between two configs."""

        lines_a = config_a.splitlines(keepends=True)
        lines_b = config_b.splitlines(keepends=True)

        diff = difflib.unified_diff(
            lines_a,
            lines_b,
            fromfile='Current',
            tofile='New',
            lineterm=''
        )

        return list(diff)

    def semantic_diff(self, config_a: str, config_b: str) -> Dict:
        """Parse and compare semantic differences."""

        parsed_a = parse_toml_config(config_a)
        parsed_b = parse_toml_config(config_b)

        changes = {
            'modules_added': [],
            'modules_removed': [],
            'params_changed': {},
        }

        # Compare enabled calculators
        set_a = set(parsed_a.enabled_opportunity_calculators)
        set_b = set(parsed_b.enabled_opportunity_calculators)

        changes['modules_added'] = list(set_b - set_a)
        changes['modules_removed'] = list(set_a - set_b)

        # Compare parameters
        for module_name in set_a & set_b:
            params_a = parsed_a.opportunity_params.get(module_name, {})
            params_b = parsed_b.opportunity_params.get(module_name, {})

            if params_a != params_b:
                changes['params_changed'][module_name] = {
                    'old': params_a,
                    'new': params_b,
                }

        return changes
```

**UI Feature**: Show diff before saving config changes.

**Implementation**: Phase 7 (UI enhancement)

---

### 3.3 Configuration Presets Library

**Problem**: Users might want to share/discover configurations.

**Solution**: Community preset library.

```sql
CREATE TABLE config_presets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    config_toml TEXT NOT NULL,
    author TEXT,
    tags TEXT,  -- JSON array
    downloads INTEGER DEFAULT 0,
    rating REAL,
    created_at TEXT NOT NULL
);
```

```python
# api/presets.py
@router.get("/presets")
async def list_presets(tag: str = None):
    """List available configuration presets."""
    # Query presets, filter by tag if provided
    pass

@router.get("/presets/{preset_id}")
async def get_preset(preset_id: str):
    """Get a specific preset configuration."""
    pass

@router.post("/presets")
async def create_preset(
    name: str,
    config_toml: str,
    description: str = None,
    tags: List[str] = None
):
    """Share a configuration as a preset."""
    pass
```

**Benefits**:
- Share successful strategies
- Learn from others
- Quick experimentation

**Implementation**: Post-launch enhancement

---

## Category 4: Testing & Validation

### 4.1 Dry-Run Mode

**Problem**: Can't test configuration without running actual planning.

**Solution**: Dry-run mode validates without side effects.

```python
# domain/planner.py
class HolisticPlanner:
    async def dry_run(self, context: PlannerContext) -> Dict:
        """
        Validate configuration without executing.

        Returns report of what would happen.
        """

        report = {
            'valid': True,
            'modules_loaded': {},
            'estimated_sequences': 0,
            'warnings': [],
            'errors': [],
        }

        # Test load all modules
        try:
            for calc in self.opportunity_calculators:
                report['modules_loaded'][calc.name] = {
                    'type': 'calculator',
                    'status': 'ok',
                    'params': calc.default_params()
                }
        except Exception as e:
            report['valid'] = False
            report['errors'].append(str(e))

        # Estimate sequence count
        num_patterns = len(self.pattern_generators)
        num_depths = self.config.max_plan_depth
        report['estimated_sequences'] = num_patterns * num_depths

        if 'combinatorial' in self.config.enabled_sequence_generators:
            report['estimated_sequences'] *= 5  # Rough estimate

        # Check for warnings
        warnings = ConfigurationValidator.check_dependencies(self.config)
        report['warnings'] = warnings

        return report
```

**API Endpoint**:
```python
@router.post("/satellites/{id}/dry-run")
async def dry_run_config(id: str, config_toml: str):
    """Test configuration without running."""

    config = parse_toml_config(config_toml)
    planner = HolisticPlanner(config=config, bucket_id=id)

    # Minimal context for validation
    context = build_minimal_context()

    report = await planner.dry_run(context)
    return report
```

**Implementation**: Phase 6

---

### 4.2 A/B Testing Framework

**Problem**: Can't compare two configurations objectively.

**Solution**: Run both configs, compare results.

```python
# services/ab_testing.py
class ABTestRunner:
    """Run A/B tests on configurations."""

    async def run_test(
        self,
        bucket_id: str,
        config_a: PlannerConfiguration,
        config_b: PlannerConfiguration,
        context: PlannerContext,
    ) -> Dict:
        """Run both configs and compare results."""

        planner_a = HolisticPlanner(config=config_a, bucket_id=f"{bucket_id}_test_a")
        planner_b = HolisticPlanner(config=config_b, bucket_id=f"{bucket_id}_test_b")

        # Run both
        plan_a = await planner_a.plan(context)
        plan_b = await planner_b.plan(context)

        # Compare
        comparison = {
            'config_a': {
                'end_score': plan_a.end_state_score if plan_a else None,
                'num_steps': len(plan_a.steps) if plan_a else 0,
                'cash_required': plan_a.cash_required if plan_a else 0,
            },
            'config_b': {
                'end_score': plan_b.end_state_score if plan_b else None,
                'num_steps': len(plan_b.steps) if plan_b else 0,
                'cash_required': plan_b.cash_required if plan_b else 0,
            },
            'winner': 'a' if (plan_a and plan_b and plan_a.end_state_score > plan_b.end_state_score) else 'b',
        }

        return comparison
```

**Implementation**: Post-launch enhancement

---

## Category 5: Module System Enhancements

### 5.1 Module Metadata & Versioning

**Problem**: No way to track module versions, compatibility.

**Solution**: Module metadata with semantic versioning.

```python
# calculations/base.py
@dataclass
class ModuleMetadata:
    """Metadata for a calculation module."""
    name: str
    version: str  # Semantic version: "1.2.3"
    author: str
    description: str
    requires_python: str = ">=3.11"
    dependencies: List[str] = field(default_factory=list)  # Other modules
    tags: List[str] = field(default_factory=list)

class CalculationModule(ABC):
    """Base class with metadata."""

    @property
    @abstractmethod
    def metadata(self) -> ModuleMetadata:
        """Return module metadata."""
        pass

# Example:
class ProfitTakingCalculator(OpportunityCalculator):
    @property
    def metadata(self) -> ModuleMetadata:
        return ModuleMetadata(
            name="profit_taking",
            version="1.0.0",
            author="Core Team",
            description="Identifies windfall positions for profit-taking",
            tags=["sell", "profit", "windfall"]
        )
```

**Benefits**:
- Version tracking
- Dependency management
- Better documentation

**Implementation**: Phase 2

---

### 5.2 Module Dependencies

**Problem**: Some modules depend on others being enabled.

**Solution**: Explicit dependency declarations.

```python
class CombinatorialGenerator(SequenceGenerator):
    @property
    def metadata(self) -> ModuleMetadata:
        return ModuleMetadata(
            name="combinatorial",
            version="1.0.0",
            dependencies=[
                "pattern_generators.single_best",  # Requires at least one pattern
            ]
        )

    def validate_dependencies(self, enabled_modules: List[str]) -> List[str]:
        """Validate dependencies are met."""
        errors = []

        # Check if at least one pattern generator is enabled
        pattern_enabled = any(
            m.startswith('pattern_generators.')
            for m in enabled_modules
        )

        if not pattern_enabled:
            errors.append(
                "Combinatorial generator requires at least one pattern generator"
            )

        return errors
```

**Validation at config load time:**
```python
class ConfigurationValidator:
    @staticmethod
    def validate_dependencies(config: PlannerConfiguration) -> List[str]:
        """Validate all module dependencies are satisfied."""

        errors = []
        enabled = (
            config.enabled_opportunity_calculators +
            config.enabled_pattern_generators +
            config.enabled_sequence_generators +
            config.enabled_filters
        )

        # Check each enabled module's dependencies
        for module_name in enabled:
            module = get_module_by_name(module_name)
            if hasattr(module, 'validate_dependencies'):
                module_errors = module.validate_dependencies(enabled)
                errors.extend(module_errors)

        return errors
```

**Implementation**: Phase 4

---

### 5.3 Plugin System

**Problem**: Can't add custom modules without modifying codebase.

**Solution**: Plugin loader for external modules.

```python
# calculations/plugin_loader.py
import importlib
from pathlib import Path

class PluginLoader:
    """Load external calculator plugins."""

    def __init__(self, plugin_dir: Path):
        self.plugin_dir = plugin_dir

    def load_plugins(self):
        """Discover and load plugins from directory."""

        if not self.plugin_dir.exists():
            return

        # Find all .py files in plugin directory
        for plugin_file in self.plugin_dir.glob("*.py"):
            try:
                # Import module
                spec = importlib.util.spec_from_file_location(
                    plugin_file.stem,
                    plugin_file
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Plugins auto-register when imported
                logger.info(f"Loaded plugin: {plugin_file.stem}")
            except Exception as e:
                logger.error(f"Failed to load plugin {plugin_file}: {e}")

# Usage in planner initialization:
plugin_loader = PluginLoader(Path("~/.arduino-trader/plugins"))
plugin_loader.load_plugins()
```

**Plugin example**:
```python
# ~/.arduino-trader/plugins/my_custom_calculator.py
from app.modules.planning.domain.calculations.opportunities.base import (
    OpportunityCalculator,
    opportunity_registry
)

class MyCustomCalculator(OpportunityCalculator):
    @property
    def metadata(self):
        return ModuleMetadata(
            name="my_custom",
            version="1.0.0",
            author="Me"
        )

    async def calculate(self, context, params):
        # Custom logic
        return []

# Auto-register
opportunity_registry.register(MyCustomCalculator())
```

**Benefits**:
- Extensibility without forking
- Community contributions
- Experimentation

**Implementation**: Post-launch

---

## Category 6: Caching & Performance

### 6.1 Calculation Caching

**Problem**: Expensive calculations repeated unnecessarily.

**Solution**: Cache calculation results with TTL.

```python
# calculations/cache.py
from functools import wraps
import hashlib
import json

class CalculationCache:
    """Cache for expensive calculations."""

    def __init__(self):
        self._cache = {}

    def key(self, calculator_name: str, context_hash: str, params: dict) -> str:
        """Generate cache key."""
        params_json = json.dumps(params, sort_keys=True)
        return f"{calculator_name}:{context_hash}:{hashlib.md5(params_json.encode()).hexdigest()}"

    def get(self, key: str):
        """Get cached result."""
        return self._cache.get(key)

    def set(self, key: str, value, ttl: int = 300):
        """Set cached result with TTL."""
        self._cache[key] = {
            'value': value,
            'expires_at': time.time() + ttl
        }

    def clear_expired(self):
        """Remove expired entries."""
        now = time.time()
        expired = [k for k, v in self._cache.items() if v['expires_at'] < now]
        for k in expired:
            del self._cache[k]

# Decorator for cacheable calculations:
def cacheable(ttl: int = 300):
    """Decorator to cache calculator results."""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, context, params):
            # Generate cache key from context hash
            context_hash = hash_context(context)
            key = cache.key(self.name, context_hash, params)

            # Check cache
            cached = cache.get(key)
            if cached and cached['expires_at'] > time.time():
                logger.debug(f"Cache hit for {self.name}")
                return cached['value']

            # Calculate
            result = await func(self, context, params)

            # Cache result
            cache.set(key, result, ttl)

            return result
        return wrapper
    return decorator

# Usage:
class ProfitTakingCalculator(OpportunityCalculator):
    @cacheable(ttl=60)  # Cache for 1 minute
    async def calculate(self, context, params):
        # Expensive calculation
        ...
```

**Implementation**: Phase 6

---

## Category 7: Documentation & Developer Experience

### 7.1 Auto-Generated Documentation

**Problem**: Module documentation gets out of sync with code.

**Solution**: Generate docs from module metadata and docstrings.

```python
# scripts/generate_module_docs.py
def generate_module_documentation():
    """Generate markdown docs for all modules."""

    docs = ["# Planner Modules\n\n"]

    # Document calculators
    docs.append("## Opportunity Calculators\n\n")
    for name, calc in opportunity_registry.get_all().items():
        docs.append(f"### {name}\n\n")
        docs.append(f"**Version**: {calc.metadata.version}\n")
        docs.append(f"**Description**: {calc.metadata.description}\n\n")
        docs.append(f"**Default Parameters**:\n```python\n")
        docs.append(json.dumps(calc.default_params(), indent=2))
        docs.append("\n```\n\n")

    # Write to file
    with open("docs/modules.md", "w") as f:
        f.write("".join(docs))
```

**Run as pre-commit hook** to keep docs fresh.

**Implementation**: Phase 8

---

### 7.2 Configuration Schema

**Problem**: No autocomplete/validation in TOML editors.

**Solution**: Generate JSON Schema for TOML configs.

```python
# config/schema_generator.py
def generate_toml_schema() -> dict:
    """Generate JSON Schema for TOML configuration."""

    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Planner Configuration",
        "type": "object",
        "properties": {
            "max_plan_depth": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "default": 5,
                "description": "Maximum plan depth (1-10)"
            },
            "opportunity_calculators": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        }
    }

    # Add all modules from registries
    for name, calc in opportunity_registry.get_all().items():
        schema["properties"]["opportunity_calculators"]["properties"][name] = {
            "oneOf": [
                {"type": "boolean"},  # Enable/disable
                {  # Or with params
                    "type": "object",
                    "properties": generate_param_schema(calc.default_params())
                }
            ]
        }

    return schema
```

**Use in IDE**: Configure VS Code/etc to use schema for autocomplete.

**Implementation**: Phase 5

---

## Priority Recommendations

### Must-Have (Include in initial implementation)
1. ✅ **Structured Event System** - Critical for observability
2. ✅ **Performance Profiling** - Identify bottlenecks early
3. ✅ **Graceful Degradation** - Reliability
4. ✅ **Configuration Versioning** - Audit trail
5. ✅ **Health Checks** - Operational visibility
6. ✅ **Module Metadata** - Foundation for dependencies
7. ✅ **Configuration Import/Export** - Backup and recovery
8. ✅ **Planner Instance Caching** - Performance

### Should-Have (Phase 7-8)
9. **Circuit Breaker** - Prevent cascading failures
10. **Dry-Run Mode** - Safe testing
11. **Configuration Diffing** - Better UX
12. **Module Dependencies** - Validate compatibility

### Nice-to-Have (Post-launch)
13. Plugin System - Extensibility
14. A/B Testing - Optimization
15. Preset Library - Community
16. Calculation Caching - Performance

---

## Category 8: Configuration Import/Export

###  8.1 Configuration File Export

**Problem**: Need backup and sharing mechanism for configurations.

**Solution**: Export/import configurations as TOML files.

```python
# services/config_import_export.py
class ConfigurationImportExport:
    """Import and export configurations as files."""

    async def export_config(
        self,
        config_id: int,
        file_path: str = None
    ) -> str:
        """
        Export configuration as TOML file.

        Args:
            config_id: Configuration ID to export
            file_path: Optional path to write file

        Returns:
            TOML string (also writes to file if path provided)
        """
        # Get configuration from database
        config = await self.config_manager.get_config_by_id(config_id)

        # Add metadata header
        toml_with_metadata = f'''# Planner Configuration Export
# Name: {config['name']}
# Title: {config['title']}
# Version: {config['version']}
# Created: {config['created_at']}
# Exported: {datetime.now().isoformat()}
#
# Description:
# {config['description']}

{config['config_toml']}
'''

        # Write to file if path provided
        if file_path:
            async with aiofiles.open(file_path, 'w') as f:
                await f.write(toml_with_metadata)

        return toml_with_metadata

    async def import_config(
        self,
        toml_content: str,
        name: str = None,
        title: str = None
    ) -> int:
        """
        Import configuration from TOML string or file.

        Args:
            toml_content: TOML configuration string
            name: Override name (extracts from metadata if not provided)
            title: Override title (extracts from metadata if not provided)

        Returns:
            New configuration ID
        """
        # Parse TOML
        import tomllib
        config_dict = tomllib.loads(toml_content)

        # Extract name/title from metadata comments if not provided
        if not name or not title:
            # Parse comments for metadata
            lines = toml_content.split('\n')
            metadata = self._extract_metadata_from_comments(lines)
            name = name or metadata.get('name', 'imported_config')
            title = title or metadata.get('title', 'Imported Configuration')

        # Validate configuration
        from app.modules.planning.domain.config.validator import ConfigurationValidator
        validator = ConfigurationValidator()
        validation_result = validator.validate(config_dict)

        if not validation_result.is_valid:
            raise ValueError(f"Invalid configuration: {validation_result.errors}")

        # Create new configuration version
        config_id = await self.config_manager.create_new_version(
            name=name,
            title=title,
            config_toml=toml_content,
            description="Imported configuration"
        )

        return config_id

    def _extract_metadata_from_comments(self, lines: list) -> dict:
        """Extract metadata from comment header."""
        metadata = {}
        for line in lines:
            if not line.startswith('#'):
                break
            if ': ' in line:
                key, value = line[1:].split(': ', 1)
                metadata[key.strip().lower()] = value.strip()
        return metadata
```

**API Endpoints**:
```python
# api/planner_config.py
@router.get("/configs/{config_id}/export")
async def export_config(config_id: int):
    """Export configuration as downloadable TOML file."""
    toml_content = await config_import_export.export_config(config_id)

    return Response(
        content=toml_content,
        media_type="text/plain",
        headers={
            "Content-Disposition": f"attachment; filename=planner_config_{config_id}.toml"
        }
    )

@router.post("/configs/import")
async def import_config(
    file: UploadFile = File(...),
    name: str = None,
    title: str = None
):
    """Import configuration from TOML file."""
    toml_content = await file.read()
    toml_string = toml_content.decode('utf-8')

    config_id = await config_import_export.import_config(
        toml_string,
        name=name,
        title=title
    )

    return {"config_id": config_id, "status": "imported"}

@router.post("/configs/{config_id}/clone")
async def clone_config(
    config_id: int,
    new_name: str,
    new_title: str
):
    """Clone existing configuration with new name."""
    # Export original
    toml_content = await config_import_export.export_config(config_id)

    # Import as new config
    new_config_id = await config_import_export.import_config(
        toml_content,
        name=new_name,
        title=new_title
    )

    return {"config_id": new_config_id, "status": "cloned"}
```

**Benefits**:
- Backup configurations as files
- Share configurations (even though single user, useful for device migration)
- Clone/fork existing configurations easily
- Version control configs in git if desired
- Disaster recovery

**Implementation**: Phase 7

---

## Category 9: Planner Instance Lifecycle & Cache Management

### 9.1 Planner Instance Caching

**Problem**: Creating planner instances is expensive (loads modules, parses config). Without caching, every planning job creates new instance.

**Solution**: Cache planner instances per bucket, invalidate on config change.

```python
# services/planner_factory.py (enhanced)
class PlannerFactory:
    """Factory for creating and caching planner instances."""

    def __init__(self):
        self._planner_cache: Dict[str, 'HolisticPlanner'] = {}
        self._config_hashes: Dict[str, str] = {}  # bucket_id -> config hash

    async def get_planner(self, bucket_id: str) -> 'HolisticPlanner':
        """
        Get planner instance for bucket.

        Uses cache if config unchanged, otherwise creates new instance.

        Args:
            bucket_id: Bucket identifier ('core', 'satellite_a', etc.)

        Returns:
            HolisticPlanner instance
        """
        # Get current configuration for bucket
        config = await self.config_manager.get_bucket_config(bucket_id)

        # Calculate config hash
        config_hash = hashlib.sha256(
            config['config_toml'].encode()
        ).hexdigest()

        # Check if cached planner is valid
        if bucket_id in self._planner_cache:
            cached_hash = self._config_hashes.get(bucket_id)

            if cached_hash == config_hash:
                # Cache hit - return cached instance
                logger.info(f"Using cached planner for bucket '{bucket_id}'")
                return self._planner_cache[bucket_id]
            else:
                # Config changed - invalidate cache
                logger.info(
                    f"Config changed for bucket '{bucket_id}', "
                    f"invalidating cache"
                )
                await self.invalidate_cache(bucket_id)

        # Cache miss or invalidated - create new planner
        logger.info(f"Creating new planner instance for bucket '{bucket_id}'")
        planner = await self._create_planner(bucket_id, config)

        # Cache the instance
        self._planner_cache[bucket_id] = planner
        self._config_hashes[bucket_id] = config_hash

        return planner

    async def invalidate_cache(self, bucket_id: str = None):
        """
        Invalidate planner cache.

        Args:
            bucket_id: Specific bucket to invalidate, or None for all
        """
        if bucket_id:
            # Invalidate specific bucket
            if bucket_id in self._planner_cache:
                logger.info(f"Invalidating planner cache for '{bucket_id}'")
                del self._planner_cache[bucket_id]
                del self._config_hashes[bucket_id]
        else:
            # Invalidate all
            logger.info("Invalidating all planner caches")
            self._planner_cache.clear()
            self._config_hashes.clear()

    async def _create_planner(
        self,
        bucket_id: str,
        config: dict
    ) -> 'HolisticPlanner':
        """Create new planner instance from configuration."""
        import tomllib
        from app.modules.planning.domain.config.planner_config import (
            parse_toml_config
        )

        # Parse TOML configuration
        planner_config = parse_toml_config(config['config_toml'])

        # Create planner instance
        planner = HolisticPlanner(
            config=planner_config,
            bucket_id=bucket_id,
            repositories=self.repositories,
            services=self.services
        )

        return planner
```

### 9.2 Configuration Change Detection

**Problem**: Need to detect when configurations change to invalidate cache.

**Solution**: Event-driven cache invalidation.

```python
# services/config_manager.py (enhanced)
class ConfigurationManager:
    """Manage planner configuration versions with cache invalidation."""

    def __init__(
        self,
        config_db_path: str = "planner_configurations.db",
        planner_factory: 'PlannerFactory' = None
    ):
        self.config_db = aiosqlite.connect(config_db_path)
        self.planner_factory = planner_factory  # For cache invalidation

    async def assign_config_to_bucket(
        self,
        bucket_id: str,
        planner_config_id: int
    ):
        """Assign configuration to bucket and invalidate cache."""

        # Assign in database
        await self.main_db.execute(
            """INSERT OR REPLACE INTO bucket_planner_configs
               (bucket_id, planner_config_id, assigned_at)
               VALUES (?, ?, ?)""",
            (bucket_id, planner_config_id, datetime.now().isoformat())
        )
        await self.main_db.commit()

        # Invalidate planner cache for this bucket
        if self.planner_factory:
            await self.planner_factory.invalidate_cache(bucket_id)

        # Emit configuration changed event
        await self.emit_event(ConfigurationChangedEvent(
            bucket_id=bucket_id,
            config_id=planner_config_id,
            timestamp=datetime.now()
        ))
```

**Benefits**:
- Fast planner access (no recreation on every job)
- Automatic cache invalidation on config changes
- Memory efficient (only cache active planners)
- Detects configuration changes automatically

**Implementation**: Phase 6 (with planner refactor)

---

## Implementation Plan

### Integration with Modularization Phases

**Phase 2 (Registry System):**
- Add ModuleMetadata to base classes
- Implement basic module versioning

**Phase 5 (Configuration System):**
- Add ConfigurationVersioning
- Implement StructuredLogger
- Generate JSON Schema

**Phase 6 (Planner Refactor):**
- Add PerformanceTracker
- Implement GracefulDegradation
- Add CircuitBreaker
- Implement DryRun mode
- **Planner Instance Caching** - NEW
- **Cache Invalidation** - NEW

**Phase 7 (Testing & Validation):**
- Add HealthChecks API
- Implement ConfigurationDiffer
- Auto-generate module docs
- **Configuration Import/Export** - NEW

**Phase 8 (Post-launch enhancements):**
- Plugin system
- A/B testing framework
- Preset library
- Calculation caching

---

## Architectural Principles

1. **Observability First** - Every operation emits events/metrics
2. **Fail Gracefully** - Partial results > no results
3. **Self-Documenting** - Metadata + auto-generated docs
4. **Performance Conscious** - Track and optimize
5. **User-Friendly** - Validation, diffing, dry-run before production
6. **Extensible** - Plugin system for customization
7. **Auditable** - Version everything, log everything

---

## Estimated Additional Time

| Enhancement | Time | Phase |
|------------|------|-------|
| Event System | 3-5 days | 5 |
| Performance Tracking | 2-3 days | 6 |
| Graceful Degradation | 2-3 days | 6 |
| Config Versioning | 3-4 days | 7 |
| Health Checks | 1-2 days | 7 |
| Module Metadata | 2-3 days | 2 |
| Circuit Breaker | 2-3 days | 6 |
| Dry-Run Mode | 2-3 days | 6 |
| Config Diffing | 2-3 days | 7 |
| **Import/Export** | **2-3 days** | **7** |
| **Planner Caching** | **1-2 days** | **6** |

**Total Additional Time: ~4-5 weeks**

**New Timeline with Enhancements: 12-17 weeks**

Worth it? **Absolutely** - These make the system production-ready, maintainable, and debuggable.
