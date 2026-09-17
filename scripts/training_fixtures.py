"""Deterministic training-only inputs. No personal configuration or validation data."""
import json
from pathlib import Path
import subprocess


def prepare(base, env):
    base.mkdir(parents=True, exist_ok=True)
    code = ''.join(f'(defun training-value-{i} (x)\n  ;; Compute a small result.\n  (+ x {i}))\n\n' for i in range(24))
    prose = '\n\n'.join([
        'Short paragraph. A needle appears here.',
        '中文段落：修改、撤销和搜索。English words and λ share this paragraph.',
        'Different line lengths matter.\nA short line.\n' + 'An ordinary longer sentence with several words. ' * 7,
        'Combining characters: cafe\u0301; punctuation: — “quoted”.\nFinal needle.']) + '\n'
    log = '\n'.join(json.dumps({'record':i, 'message':'training needle' if i % 5 == 0 else 'ordinary entry',
                                 'values':list(range(220 if i % 9 == 0 else i % 7))},ensure_ascii=False)
                    for i in range(45)) + '\n'
    for name,text in [('edit.el',code),('prose.txt',prose),('mixed-lines.txt',log)]:
        (base / name).write_text(text)
    org = '''#+title: Training notebook
* Planning
:PROPERTIES:
:ID: training-plan
:END:
** TODO First task
Some [[https://example.invalid/guide][reference]] text; never follow the external link.
*** Details
**** Deep detail
Text below a deep heading.
** Measurements
| Item | Count |
|------+-------|
| alpha | 12 |
| beta | 34 |
** Code
#+begin_src emacs-lisp
(defun training-double (x)
  (* 2 x))
#+end_src
* Notes
A second top-level heading.
'''
    (base / 'notebook.org').write_text(org)
    for parent in ('project alpha/src','project alpha/docs','project beta/src'):
        directory=base / 'completion' / parent
        directory.mkdir(parents=True)
        for name in ('common-first.txt','common-final.txt','common-file notes.txt'):
            (directory / name).write_text(f'Training completion: {parent}/{name}\n')
    repos = {}
    for kind,count,commits in [('small',5,3),('medium',40,8)]:
        repo = base / ('repository-' + kind)
        repo.mkdir()
        def git(*args):
            return subprocess.check_output(['git','-C',str(repo),*args],env=env,stderr=subprocess.STDOUT,text=True)
        git('init','-q','-b','main');git('config','user.name','Training Fixture')
        git('config','user.email','training@example.invalid');git('config','commit.gpgsign','false')
        for n in range(count):
            (repo/f'unit-{n:02d}.c').write_text(''.join(f'int value_{n}_{i} = {i};\n' for i in range(160)))
        git('add','.');git('commit','-qm','Training initial')
        for n in range(commits):
            path=repo/f'unit-{n:02d}.c'
            path.write_text(path.read_text()+f'/* revision {n} */\n')
            git('add','.');git('commit','-qm',f'Training revision {n}')
        changed = 5 if kind == 'small' else 12
        for n in range(changed):
            path=repo/f'unit-{n:02d}.c'
            path.write_text(path.read_text().replace(' = 9;', ' = 471;').replace(' = 110;', ' = 819;')+'/* pending edit */\n')
        if kind == 'medium':
            git('add','unit-00.c','unit-01.c','unit-02.c')
            (repo/'untracked notes.txt').write_text('Training-only untracked file.\n')
        repos[kind]=(repo,changed)
    return repos
