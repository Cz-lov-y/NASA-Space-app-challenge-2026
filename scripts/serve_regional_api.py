"""Run the local globe backend. Live provider access is explicitly opt-in."""
import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from scripts.run_regional_research import read_settings
from src.regional_api import RegionalAPI,make_server


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--directory',type=Path,default=ROOT/'data/processed/regional')
    parser.add_argument('--env-file',type=Path,default=ROOT/'.env')
    parser.add_argument('--enable-live',action='store_true',help='Allow explicit research POSTs to use server provider credentials')
    args=parser.parse_args(argv)
    api=None
    try:
        settings=read_settings(args.env_file) if args.enable_live else {}
        api=RegionalAPI(directory=args.directory,settings=settings,live_enabled=args.enable_live)
        server=make_server(api,port=args.port)
    except (ValueError,OSError):
        if api:
            api.close()
        print('Could not start local API; check port, settings and data paths.',file=sys.stderr)
        return 2
    print(f'Local regional API: http://127.0.0.1:{server.server_port}; live research {"enabled" if args.enable_live else "disabled"}.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        api.close()
    return 0


if __name__=='__main__':
    raise SystemExit(main())
