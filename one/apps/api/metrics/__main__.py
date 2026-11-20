"""``python -m api.metrics purge --organization <uuid>`` : voir ``api.metrics.jobs``."""

from __future__ import annotations

from api.metrics.jobs import main

raise SystemExit(main())
