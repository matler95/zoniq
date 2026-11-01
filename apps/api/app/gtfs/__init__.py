"""GTFS validation, provenance, and normalization primitives."""

from .ingestion import FeedReport, GTFSValidationError, inspect_feed, scope_id, write_report

__all__ = ["FeedReport", "GTFSValidationError", "inspect_feed", "scope_id", "write_report"]
