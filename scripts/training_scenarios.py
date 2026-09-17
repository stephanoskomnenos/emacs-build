"""Real PTY actions and assertions for generic training subscenarios."""
from training_input import cancel_minibuffer

# Outer group targets stay in pgo-train.py; each group's cases receive equal
# execution-count shares, independently of file size or runtime.
GROUPS = {
    'files': ['files'],
    'editing': ['editing-code','editing-prose','editing-log'],
    'minibuffer': ['minibuffer-commands','minibuffer-paths'],
    'org': ['org-news','org-structure'],
    'process': ['process-fragmented','process-batched'],
    'magit': ['magit-small','magit-medium'],
}


def exercise(name, session, corpus, fixtures, repos, git, producer):
    recorded=[]
    def action(keys, check=lambda state: True):
        state=session.action(keys)['state']
        if not check(state):
            raise RuntimeError(f'{name}: unexpected training result {state}')
        recorded.append({k:v for k,v in state.items() if k not in ('text','compilation_output')})
        return state
    def command(name):
        return b'\x1bx' + name.encode() + b'\r'
    def open_file(path):
        return action(b'\x18\x06'+str(path).encode()+b'\r',lambda s:s['file']==str(path))
    def search(text):
        return action(b'\x1b<\x13'+text.encode()+b'\r')
    if name=='files':
        action(b'\x1b[17~',lambda s:s['value']==4)
    elif name.startswith('editing-'):
        filename={'editing-code':'edit.el','editing-prose':'prose.txt','editing-log':'mixed-lines.txt'}[name]
        text=(fixtures/filename).read_text()
        state=open_file(fixtures/filename)
        assert state['size']==len(text)
        mode='emacs-lisp-mode' if name=='editing-code' else 'text-mode'
        action(command(mode),lambda s:s['mode']==mode)
        # Different positions and line lengths, using actual terminal events.
        action(b'\x1b<')
        inserted=';; temporary edit\n' if name=='editing-code' else '临时 edit\n'
        action(inserted.encode(),lambda s:s['size']==len(text)+len(inserted))
        action(b'\x15' + b'2\x1f',lambda s:s['size']==len(text))
        target='training-value-12' if name=='editing-code' else 'needle'
        search(target)
        action(b'\x01\x00\x05\x17',lambda s:s['size']<len(text))  # Select a line, kill it.
        action(b'\x19',lambda s:s['size']==len(text))
        action(b'\x1b>')
        action(b'end-marker',lambda s:s['size']==len(text)+10)
        action(b'\x15' + b'10\x7f',lambda s:s['size']==len(text))
        for _ in range(4):
            action(b'\x10\x01\x05\x0e',lambda s:s['size']==len(text))
        open_file(corpus/'files.el')
        action(b'\x18b'+filename.encode()+b'\r',lambda s:s['buffer']==filename and s['size']==len(text))
    elif name=='minibuffer-commands':
        for filename in ('news.txt','buffer.c','files.el'):
            open_file(corpus/filename)
            action(b'\x1bxend-of-buff\t\r',lambda s:s['point']==s['size']+1)
            action(b'\x1bxbeginn\t\x1bOR',lambda s:s['minibuffer_depth']==1)
            cancel_minibuffer(session)
            action(b'\x18b*scratch*\r',lambda s:s['buffer']=='*scratch*')
    elif name=='minibuffer-paths':
        root=fixtures/'completion'
        for directory in ('project alpha/src','project beta/src','project alpha/docs'):
            prefix=str(root/directory/'common-fi').encode()
            # TAB exposes ambiguous candidates; then replace input and select
            # an existing path containing spaces. No completion UI assumptions.
            action(b'\x18\x06'+prefix+b'\t',lambda s:s['minibuffer_depth']==1)
            target=root/directory/'common-file notes.txt'
            action(b'\x01\x0b'+str(target).encode()+b'\r',lambda s:s['file']==str(target))
            action(b'\x18\x06'+prefix+b'\t\x1bOR',lambda s:s['minibuffer_depth']==1)
            cancel_minibuffer(session)
            open_file(root/directory/'common-final.txt')
    elif name=='org-news':
        action(b'\x1b[20~',lambda s:s['mode']=='org-mode')
        for _ in range(4):action(b'\t\x0e\x0e\x10',lambda s:s['mode']=='org-mode')
        action(b'\x1b>\r* Training heading\r- item one\r- item two\r',lambda s:s['mode']=='org-mode')
    elif name=='org-structure':
        open_file(fixtures/'notebook.org')
        action(command('org-show-all'))
        search('Deep detail')
        action(b'\x01\t\t',lambda s:s['mode']=='org-mode')
        search('alpha')
        action(command('org-table-align'),lambda s:'| alpha' in s['text'])
        action(command('org-table-next-field'))
        search('training-double')
        action(b'\x03\x27',lambda s:s['mode']=='emacs-lisp-mode')  # org-edit-special
        size=action(b'\x1b>')['size']
        action(b'\n;; Edited through Org source buffer\n',lambda s:s['size']>size)
        action(b'\x03\x27',lambda s:s['mode']=='org-mode' and 'Edited through Org' in s['text'])
        search('reference')
        action(command('org-toggle-link-display'),lambda s:s['mode']=='org-mode')
        action(b'\x1b<'+command('org-overview'))
        action(command('org-show-all'),lambda s:'training-plan' in s['text'])
    elif name.startswith('process-'):
        action(b'\x1b[19~',lambda s:s['frames']==180 and s['value']==180*179//2 and s['retained']==9 and s['filter_calls']>0)
        if name=='process-batched':
            shell='python3 '+str(producer)+' compile'
            action(command('compile')+b'\x01\x0b'+shell.encode()+b'\r',
                   lambda s:s['compilation_status']=='finished' and 'training diagnostic' in s['compilation_output'])
    elif name.startswith('magit-'):
        kind=name.split('-',1)[1];repo,changed=repos[kind]
        if kind=='medium':assert len(git(repo,'diff','--cached','--name-only').splitlines())==3
        action(b'\x15'+command('magit-status')+str(repo).encode()+b'\r',lambda s:s['mode']=='magit-status-mode')
        action(command('magit-log-current'),lambda s:s['mode']=='magit-log-mode')
        action(b'q',lambda s:s['mode']=='magit-status-mode')
        action(command('magit-stage-modified')+(b'y' if kind=='medium' else b''))
        assert len(git(repo,'diff','--cached','--name-only').splitlines())==changed
        action(command('magit-unstage-all')+(b'y' if kind=='medium' else b''))
        assert not git(repo,'diff','--cached','--name-only').strip()
        action(command('magit-jump-to-unstaged')+b'n\t',lambda s:'@@' in s['text'])
        action(b'g',lambda s:s['mode']=='magit-status-mode')
    else:
        raise ValueError(name)
    return recorded
