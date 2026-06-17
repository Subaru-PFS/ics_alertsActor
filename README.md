# ics_alertsActor

MHS Actor which forwards keywords to the Subaru Telemetry System (STS) and which generates and manages MHS alerts for
the Subaru PFS project.

## Overview

The `alertsActor` acts as a bridge between MHS (Messaging Hub System) keywords and the Subaru Telemetry System. it
monitors keywords from various actors (e.g., `xcu`, `enu`, `rough`) and triggers alerts based on configurable logic.

## Architecture

### Alert Flow

The `alertsActor` operates on a push-based mechanism using MHS (Messaging Hub System) keyword callbacks.

1. **Subscription**: For each monitored actor (e.g., `xcu`, `enu`), the `alertsActor` subscribes to specific keywords
   defined in `STS.yaml`.
2. **Reception**: When a monitored actor updates a keyword, MHS triggers a callback in the corresponding `KeyCallback`
   instance.
3. **Processing**:
    * The `KeyCallback` converts the new keyword value into a standardized "STS Datum".
    * It evaluates the value against configured alert logic (limits, boolean, or regular expressions).
    * If the value has changed significantly or if a transmit rate limit is reached, it prepares the data for
      transmission.
4. **Transmission**:
    * Data is forwarded to the Subaru Telemetry System (STS) via the `subaru-telemetry-client` library.
    * If an alert is triggered or cleared, the actor updates its internal state and generates an `alertStatus` keyword.
5. **Monitoring**: The actor also performs periodic checks for "stale" data (timeouts), ensuring that if an actor stops
   reporting, an alert is still generated.

### Core Components

- **`OurActor` (`main.py`)**: The main orchestration class. It initializes connections to other actors, manages the
  lifecycle of controllers, and generates the overall `alertStatus`.
- **`ActorRules` (`Controllers/actorRules.py`)**: A base class for all hardware-specific controllers. Each controller
  runs in its own `QThread` and manages the subscriptions and alert logic for a single actor model.
- **`KeyCallback` (`utils/keyCallback.py`)**: The entry point for incoming data. It handles keyword updates and
  coordinates with `Key` objects to determine if data should be transmitted or if an alert is warranted.
- **`Key` (`utils/key.py`)**: Represents a single field within a keyword. It maintains the state of a specific telemetry
  point, including its alert logic and transmission history.
- **`AlertsFactory` (`utils/alertsFactory.py`)**: A factory that creates specialized `Alert` objects (Limits, Regexp,
  Boolean) based on the configurations loaded from `pfs_instdata`.

### Controllers

Controllers are located in `python/alertsActor/Controllers/`. They map specific hardware types to monitoring rules.

- **Hardware-Specific Logic**: Some controllers like `xcu.py` and `rough.py` contain custom Python logic for complex
  monitoring (e.g., cryo-mode transitions or cross-actor dependencies).
- **Placeholder/Stub Controllers**: Files like `enu.py`, `meb.py`, and `peb.py` may appear empty (only inheriting from
  `ActorRules`). These are **functional placeholders** that:
    1. Allow the actor to dynamically load and connect to these models.
    2. Provide a designated location for future custom logic.
    3. Isolate the monitoring of different hardware types into separate threads.

## Configuration

Configuration files are managed via the [**`pfs_instdata`**](https://github.com/Subaru-PFS/pfs_instdata) package and are typically located in the `config/alerts/`
directory of that repository.

- **`STS.yaml`**: Defines the mapping between MHS keywords and STS radio IDs.
- **`keywordAlerts.yaml`**: Defines the alert logic (types, limits, etc.) for specific keywords.

## Development & Maintenance


### Utilities
None at this moment.
