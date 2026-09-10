(() => {
  const status = document.getElementById('state');
  const fileLabel = document.getElementById('file');
  const projectLabel = document.getElementById('project');
  const fileHost = document.getElementById('files');
  const filter = document.getElementById('filter');
  const saveButton = document.getElementById('save');
  let editor = null;
  let currentPath = '';
  let allFiles = [];
  let options = {};

  const bridge = () => window.pywebview && window.pywebview.api;
  function language(path){const x=(path.split('.').pop()||'').toLowerCase();return ({py:'python',rs:'rust',js:'javascript',ts:'typescript',json:'json',toml:'ini',ron:'plaintext',md:'markdown',cpp:'cpp',cc:'cpp',c:'c',h:'cpp',hpp:'cpp',cs:'csharp',java:'java',ps1:'powershell',html:'html',css:'css',xml:'xml',yaml:'yaml',yml:'yaml'}[x]||'plaintext');}
  function renderFiles(){
    const q=(filter.value||'').toLowerCase(); fileHost.innerHTML='';
    allFiles.filter(x=>!q||x.toLowerCase().includes(q)).slice(0,20000).forEach(path=>{
      const row=document.createElement('div'); row.className='file-row'+(path===currentPath?' active':''); row.textContent=path; row.title=path; row.onclick=()=>openFile(path); fileHost.appendChild(row);
    });
  }
  async function bootstrap(){
    const api=bridge(); if(!api){status.textContent='Bridge unavailable';return;}
    try{
      const boot=await api.bootstrap(); allFiles=boot.files||[]; options=boot.options||{}; projectLabel.textContent=boot.projectName||'Project'; renderFiles();
      if(editor){editor.updateOptions({fontSize:Number(options.fontSize||13),wordWrap:options.wordWrap||'off',minimap:{enabled:options.minimap!==false}});}
      status.textContent='Ready'; if(boot.initialFile) await openFile(boot.initialFile);
    }catch(e){status.textContent='Bootstrap failed';console.error(e);}
  }
  require.config({ paths: { vs: 'node_modules/monaco-editor/min/vs' } });
  require(['vs/editor/editor.main'], () => {
    monaco.editor.defineTheme('vault-dark', {base:'vs-dark',inherit:true,rules:[],colors:{'editor.background':'#090b0e','editor.foreground':'#edf2f5','editorLineNumber.foreground':'#53606b','editorCursor.foreground':'#00d9ff','editor.selectionBackground':'#21404a','editor.lineHighlightBackground':'#11151a','editorIndentGuide.background1':'#28313a','editorWidget.background':'#11151a','editorWidget.border':'#28313a','focusBorder':'#00d9ff'}});
    editor=monaco.editor.create(document.getElementById('editor'),{value:'// Forge IDE\n',language:'plaintext',theme:'vault-dark',automaticLayout:true,minimap:{enabled:true},fontSize:13,fontFamily:'Cascadia Code, Consolas, monospace',smoothScrolling:true,scrollBeyondLastLine:false,wordWrap:'off'});
    editor.addCommand(monaco.KeyMod.CtrlCmd|monaco.KeyCode.KeyS, save);
    editor.onDidChangeModelContent(()=>{if(currentPath)status.textContent='Modified';});
    if(bridge()) bootstrap(); else status.textContent='Waiting for Vault…';
  });
  async function openFile(path){if(!editor||!bridge())return; status.textContent='Opening…'; try{const r=await bridge().read_file(path); currentPath=r.relative||path; fileLabel.textContent=currentPath; const model=monaco.editor.createModel(r.text,language(currentPath)); const old=editor.getModel(); editor.setModel(model); if(old)old.dispose(); status.textContent='Ready'; renderFiles();}catch(e){status.textContent='Open failed';console.error(e);}}
  async function save(){if(!editor||!currentPath||!bridge())return;status.textContent='Saving…';try{const r=await bridge().write_file(currentPath,editor.getValue());status.textContent=`Saved · ${r.bytes||0} B`;}catch(e){status.textContent='Save failed';console.error(e);}}
  filter.addEventListener('input',renderFiles); saveButton.addEventListener('click',save);
  window.addEventListener('pywebviewready',bootstrap);
  window.vaultIde={openFile,save};
})();
