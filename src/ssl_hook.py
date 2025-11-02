import os
import sys
import ssl
import certifi
import requests.certs

def configure_ssl():
    """Configure SSL certificate paths for frozen executable."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        bundle_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        
        # Check certificate locations in order of preference
        cert_locations = [
            os.path.join(bundle_dir, 'cacert.pem'),
            os.path.join(bundle_dir, 'config', 'cacert.pem'),
            os.path.join(os.path.dirname(bundle_dir), 'config', 'cacert.pem'),
            certifi.where(),
            requests.certs.where()
        ]
        
        # Use first valid certificate file found
        for cert_path in cert_locations:
            if os.path.isfile(cert_path) and os.access(cert_path, os.R_OK):
                os.environ['SSL_CERT_FILE'] = cert_path
                os.environ['REQUESTS_CA_BUNDLE'] = cert_path
                ssl._create_default_https_context = ssl._create_unverified_context
                break

# Execute hook when module is imported
configure_ssl()