"""
Admin Suite v5 — modular rewrite.
"""

__version__ = "5.0.0"


def _apply_paramiko_compat():
    """
    Compatibility patch for newer Paramiko builds where DSSKey may be missing.

    sshtunnel may reference paramiko.DSSKey during SSH tunnel setup.
    If the attribute is missing, provide a safe placeholder.
    """
    try:
        import paramiko
    except Exception:
        return

    if hasattr(paramiko, "DSSKey"):
        return

    try:
        from paramiko.pkey import PKey
    except Exception:
        class PKey:
            pass

    class DSSKey(PKey):
        name = "ssh-dss"

        def __init__(self, *args, **kwargs):
            raise NotImplementedError(
                "DSS/DSA keys are not supported by this Paramiko build."
            )

    paramiko.DSSKey = DSSKey

    for module_name in (
        "paramiko.pkey",
        "paramiko.transport",
        "paramiko.hostkeys",
        "paramiko.dsskey",
    ):
        try:
            module = __import__(module_name, fromlist=["DSSKey"])

            if not hasattr(module, "DSSKey"):
                setattr(module, "DSSKey", DSSKey)

        except Exception:
            pass


_apply_paramiko_compat()