## 1. Add Subcommand enum

- [ ] 1.1 In `src/oci_runtime/domain/enums.py`, add `class Subcommand(str, Enum)` with members: RUN="run", BUILD="build", TAG="tag", PUSH="push", PULL="pull", RMI="rmi", RM="rm", EXEC="exec", LOGS="logs", INSPECT="inspect", STOP="stop", START="start", RESTART="restart", PRUNE="prune", CREATE="create", CONNECT="connect", DISCONNECT="disconnect", LIST="list", IMAGE="image", CONTAINER="container", VOLUME="volume", NETWORK="network".
- [ ] 1.2 Add `test_subcommand_values` to `tests/unit/domain/test_enums.py` asserting `Subcommand.INSPECT.value == "inspect"` etc. for all members.
- [ ] 1.3 Assert `"Subcommand" not in oci_runtime.__all__` in the same test.

## 2. Migrate container manager

- [ ] 2.1 In `src/oci_runtime/adapters/managers/container.py`, replace all string-literal subcommands with `Subcommand.X.value`. Import `from oci_runtime.domain.enums import Subcommand`.
- [ ] 2.2 Run `uv run pytest -q tests/unit/adapters/test_cli_container_manager.py` — green.

## 3. Migrate image manager

- [ ] 3.1 Same migration in `src/oci_runtime/adapters/managers/image.py`.
- [ ] 3.2 Run `uv run pytest -q tests/unit/adapters/test_cli_image_manager.py` — green.

## 4. Migrate volume + network managers

- [ ] 4.1 Same migration in `src/oci_runtime/adapters/managers/volume.py` and `network.py`.
- [ ] 4.2 Run `uv run pytest -q tests/unit/adapters/test_cli_volume_manager.py tests/unit/adapters/test_cli_network_manager.py` — green.

## 5. Verify

- [ ] 5.1 Run `uv run pytest -q` — full suite green.
- [ ] 5.2 Run `uv run ruff check .` — green.
- [ ] 5.3 Grep: `rg -n '"(run|build|inspect|tag|push|pull|rmi|rm|exec|logs|stop|start|restart|prune|create|connect|disconnect|list|image|container|volume|network)"' src/oci_runtime/adapters/managers/` — should return zero string-literal matches (all migrated to enum).