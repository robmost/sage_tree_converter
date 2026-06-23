"""errors.py - Shared exception types for the conversion engine.

Drivers raise ``ConversionError`` (instead of calling ``sys.exit(1)``) when a
conversion fails with a known cause. ``main_driver.convert_one`` propagates the
message verbatim, so ``runner.batch_runner`` can surface the real cause in
``JobResult.error`` - including across worker processes, where a driver's stderr
would otherwise be lost.
"""


class ConversionError(Exception):
    """Raised by a driver when a conversion fails with a known cause.

    The exception message must describe the actual failure (e.g. a parse error
    or a missing field) so it can be reported to the user unchanged.
    """
