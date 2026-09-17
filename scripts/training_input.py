"""Training-only input coordination, separate from frozen validation."""
import os

def cancel_minibuffer(session):
    # C-] is dispatched after the ACK callback returns. Asynchronous C-g can
    # interrupt that callback instead of quitting the active minibuffer.
    os.write(session.fd,b'\x1d')
    session.receive('cancelled',10)
