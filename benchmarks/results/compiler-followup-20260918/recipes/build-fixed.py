"""Keep pre-link ordinary-PGO compilation identical; apply CS only at LTO link.
Execute a recorded recipe adjustment with distinct stage names, retaining the
original source/dependency paths required by the existing ordinary profile.
"""
from pathlib import Path
p=Path('/work/scripts/build.py');s=p.read_text()
s=s.replace("stable_locals = os.environ.get('STABLE_LOCALS', '0') == '1'",'stable_locals = False')
s=s.replace("variant = 'llvm-' + profile_mode + ('-stable' if stable_locals else '')","variant = 'llvm-' + profile_mode + '-linkcs'")
s=s.replace("'CFLAGS': env['CFLAGS'].replace('-fPIC', '-fPIE') + pgo_flags", "'CFLAGS': env['CFLAGS'].replace('-fPIC', '-fPIE') + ' -fprofile-use=/work/build/merged.profdata'")
s=s.replace("'emit_relocs': True,", "'emit_relocs': True, 'cs_link_only': True, 'compile_profile': '/work/build/merged.profdata',")
exec(compile(s,str(p),'exec'),{'__name__':'__main__','__file__':str(p)})
