/* ============================================================
   饭心 · 银龄放心单 — 统一交互逻辑
   包含 A-01 ~ A-05 全部页面逻辑 + PageManager 路由
   ============================================================ */
(function(){
'use strict';

// ===== PageManager 路由 =====
var PageManager = {
  current: 'home',
  pages: {},
  _history: [],
  init: function(){
    var self = this;
    var all = document.querySelectorAll('.page');
    all.forEach(function(p){
      self.pages[p.id.replace('page-','')] = p;
    });
    // 返回按钮
    document.querySelectorAll('[data-back]').forEach(function(btn){
      btn.addEventListener('click',function(){
        self.navigate(this.getAttribute('data-back'));
      });
    });
  },
  navigate: function(name, opts){
    opts = opts || {};
    // 防御：切换页面时隐藏可能遮挡的顶层遮罩，避免点击无响应
    var cancelOv=document.getElementById('cancelConfirmOverlay'); if(cancelOv) cancelOv.style.display='none';
    var voiceOv=document.getElementById('voiceErrorOverlay'); if(voiceOv) voiceOv.style.display='none';
    if(this.current===name) return;
    var old = this.pages[this.current];
    var nue = this.pages[name];
    if(!nue){console.warn('PageManager: unknown page "'+name+'"');return;}
    if(!opts.noHistory) this._history.push(this.current);
    if(old){ old.classList.remove('page--active'); }
    if(nue){ nue.classList.add('page--active'); }
    // 触发页面的 onEnter 和 onLeave（异常不影响页面切换）
    try{
      if(this.current && this.pageHooks[this.current] && this.pageHooks[this.current].onLeave){
        this.pageHooks[this.current].onLeave();
      }
    }catch(err){ console.warn('onLeave 异常:', err); }
    this.current = name;
    // 底部导航高亮由当前页面决定，避免返回时高亮停留在旧项
    var navMap = {home:'home', orders:'orders', profile:'profile'};
    var nk = navMap[name], pv = this.pages[name];
    if(nk && pv){
      var navEl = pv.querySelector('.bottom-nav');
      if(navEl) navEl.querySelectorAll('.nav-item').forEach(function(n){
        n.classList.toggle('nav-item--active', n.getAttribute('data-page') === nk);
      });
    }
    try{
      if(this.pageHooks[name] && this.pageHooks[name].onEnter){
        this.pageHooks[name].onEnter();
      }
    }catch(err){ console.warn('onEnter 异常:', err); }
    window.scrollTo({top:0,behavior:'smooth'});
  },
  // 返回上一页；无历史时回退到 fallback
  back: function(fallback){
    var target=null;
    while(this._history.length){
      var t=this._history.pop();
      if(t!==this.current&&this.pages[t]){ target=t; break; }
    }
    if(!target) target=fallback||'home';
    this.navigate(target, {noHistory:true});
  },
  pageHooks: {}
};

// ===== 留言发送者称呼 =====
var FAMILY_NAMES={'family_001':'家人','family_002':'女儿','family_003':'儿子'};
function msgSenderName(msg){
  var name=msg&&msg.sender;
  if(name&&String(name).trim()) return String(name).trim();
  return (msg&&FAMILY_NAMES[msg.family_id])||'家人';
}

// ===== 全局导航事件委托 =====
// 无论各页面模块是否初始化成功，底部状态栏点击始终可用
document.addEventListener('click', function(e){
  var item = e.target && e.target.closest ? e.target.closest('.nav-item[data-page]') : null;
  if(!item) return;
  var page = item.getAttribute('data-page');
  if(!page || !PageManager.pages[page]) return;
  PageManager.navigate(page);
});

// ===== 全局 Toast =====
var toastEl = document.getElementById('toast'), toastTimer = null;
function showToast(msg, type){
  if(!type) type='info';
  if(toastTimer) clearTimeout(toastTimer);
  toastEl.textContent=msg; toastEl.className='toast toast--visible';
  if(type==='error') toastEl.classList.add('toast--error');
  if(type==='success') toastEl.classList.add('toast--success');
  toastTimer=setTimeout(function(){toastEl.classList.remove('toast--visible');},2500);
}

// ===== 服务器连接失败提示（后端未启动/断开时弹出，防刷屏：显示期间只弹一次）=====
var serverErrorShown=false;
window.__onServerError=function(){
  if(serverErrorShown) return;
  serverErrorShown=true;
  var el=document.getElementById('serverErrorOverlay'); if(el) el.style.display='flex';
};
(function(){
  var btn=document.getElementById('serverErrorBtn');
  if(btn) btn.addEventListener('click',function(){
    var el=document.getElementById('serverErrorOverlay'); if(el) el.style.display='none';
    serverErrorShown=false;
  });
})();

// ===== 全局工具：为餐食补充图片地址（供工作流/推荐页共用）=====
function ensureMealImage(m){
  if(!m||!m.id) return m;
  var imageId=m.image_id||(m.id+'_ui');
  if(!m.image_url&&imageId) m.image_url='/elder/images/'+imageId+'.png';
  return m;
}
// 设置餐品图片（带版本号防缓存）；url 为空或加载失败则显示占位图
function setMealImg(imgEl, phEl, url){
  if(!imgEl) return;
  if(!url){ imgEl.style.display='none'; if(phEl) phEl.style.display='flex'; return; }
  imgEl.onerror=function(){ imgEl.style.display='none'; if(phEl) phEl.style.display='flex'; };
  imgEl.src=url+(url.indexOf('?')>=0?'&':'?')+'v=20260802';
  imgEl.style.display='block';
  if(phEl) phEl.style.display='none';
}
// 订单数据无图片时按 meal_id 兜底获取（返回后回调更新界面）
function fetchMealImage(mealId, onDone){
  API.getMealById(mealId).then(function(r){
    if(!r.error&&r.data&&r.data.image_url){ onDone && onDone(r.data.image_url); }
  }).catch(function(){});
}

// ================================================================
// PAGE 01: AI 首页
// ================================================================
(function(){
var DOM={}, isRecording=false, recentOrder=null, voiceMaxTimer=null, voicePermDenied=false;
// 语音采集（MediaRecorder → 解码 → WAV；降级 ScriptProcessor → PCM → WAV）
var mediaStream=null, sourceNode=null, processorNode=null, gainNode=null, pcmSamples=[];
var TARGET_RATE=16000, MAX_RECORD_MS=15000;

function setGreeting(){
  var h=new Date().getHours(), g;
  if(h>=5&&h<9) g='早上好 ☀️';
  else if(h>=9&&h<11) g='上午好 🌤️';
  else if(h>=11&&h<14) g='中午好 👋';
  else if(h>=14&&h<18) g='下午好 🌈';
  else g='晚上好 🌙';
  var display=g;
  // 称呼根据个人信息的姓 + 性别判断
  var saved=localStorage.getItem('elderProfile');
  if(saved){
    try{
      var p=JSON.parse(saved);
      var name=p&&p.name?String(p.name).trim():'';
      if(name){
        var hasTitle=/奶奶|爷爷|阿姨|叔叔|伯伯|女士|先生/.test(name);
        var title;
        if(hasTitle){ title=name; }
        else{
          title=name.charAt(0)+(p.gender==='男'?'爷爷':'奶奶');
        }
        display=title+'，'+g;
      }
    }catch(e){}
  }
  DOM.greetingTitle.textContent=display;
}
function setWeather(){
  var n=new Date(), m=n.getMonth()+1, d=n.getDate(), wd=['周日','周一','周二','周三','周四','周五','周六'][n.getDay()];
  DOM.weatherDate.textContent=m+'月'+d+'日 '+wd;
  DOM.weatherTemp.textContent='--°';
  DOM.weatherDesc.textContent='获取中';
  fetchWeather();
}
function getGeoPosition(){
  return new Promise(function(resolve){
    if(!navigator.geolocation){ resolve(null); return; }
    navigator.geolocation.getCurrentPosition(resolve,function(){resolve(null);},{timeout:5000,maximumAge:600000});
  });
}
async function fetchWeather(){
  var pos=await getGeoPosition();
  var lat=pos&&pos.coords?pos.coords.latitude:null, lon=pos&&pos.coords?pos.coords.longitude:null;
  var r=await API.getWeather(lat,lon);
  if(!r.error&&r.data){
    if(r.data.date) DOM.weatherDate.textContent=r.data.date;
    if(r.data.icon) DOM.weatherIcon.textContent=r.data.icon;
    if(r.data.temp!=null) DOM.weatherTemp.textContent=Math.round(r.data.temp)+'°';
    if(r.data.condition) DOM.weatherDesc.textContent=r.data.condition;
  }else{
    DOM.weatherDesc.textContent='天气获取失败';
  }
}

// ===== 语音采集（MediaRecorder 录制 → 解码 → WAV → 后端 ASR）=====
var mediaRecorder=null, recChunks=[], captureMode=''; // 'recorder' | 'script'

function showVoiceError(msg){
  document.getElementById('voiceErrorDesc').textContent=msg;
  document.getElementById('voiceErrorOverlay').style.display='flex';
}
function hideVoiceError(){ document.getElementById('voiceErrorOverlay').style.display='none'; }

function startCapture(){
  if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia){
    isRecording=false; resetVoiceUI();
    showVoiceError('当前页面不是安全环境，浏览器禁止调用麦克风。\n请通过 http://localhost:8000/elder/ 打开本页，或部署到 HTTPS 后即可使用语音。');
    return;
  }
  if(mediaStream){
    // 已有媒体流则直接复用，避免每次按下都弹权限询问
    beginRecording(mediaStream);
    return;
  }
  navigator.mediaDevices.getUserMedia({audio:true}).then(function(stream){
    mediaStream=stream; // 长期持有，会话内复用
    if(!isRecording){ resetVoiceUI(); return; } // 授权期间已松开：流保留待下次用，不立即 stop
    beginRecording(stream);
  }).catch(function(err){
    isRecording=false; resetVoiceUI();
    if(err&&err.name==='NotAllowedError'){ voicePermDenied=true; showVoiceError('麦克风权限被拒绝。\n请点击浏览器地址栏的麦克风图标允许访问后重试，或直接输入文字。'); }
    else showVoiceError('无法访问麦克风：'+(err&&err.message||'未知错误，请检查系统麦克风权限'));
  });
}
function beginRecording(stream){
  try{
    var MR=window.MediaRecorder;
    if(!MR){ throw new Error('MediaRecorder 不可用'); }
    mediaRecorder=new MR(stream);
    recChunks=[];
    captureMode='recorder';
    mediaRecorder.ondataavailable=function(e){ if(e.data&&e.data.size>0) recChunks.push(e.data); };
    mediaRecorder.onstop=function(){ finalizeRecording(); };
    mediaRecorder.start();
  }catch(err){
    console.warn('MediaRecorder 不可用，降级 ScriptProcessor:',err);
    fallbackStartCapture(stream);
  }
}
function fallbackStartCapture(stream){
  captureMode='script';
  try{
    var ctx=new(window.AudioContext||window.webkitAudioContext)();
    if(ctx.state==='suspended') ctx.resume();
    sourceNode=ctx.createMediaStreamSource(stream);
    var ratio=ctx.sampleRate/TARGET_RATE;
    pcmSamples=[];
    processorNode=ctx.createScriptProcessor(4096,1,1);
    processorNode.onaudioprocess=function(e){
      if(!isRecording) return;
      var data=e.inputBuffer.getChannelData(0);
      for(var i=0;i<data.length;i+=ratio){
        var s=data[Math.floor(i)];
        s=Math.max(-1,Math.min(1,s));
        pcmSamples.push(s<0?s*0x8000:s*0x7FFF);
      }
    };
    gainNode=ctx.createGain(); gainNode.gain.value=0;
    sourceNode.connect(processorNode); processorNode.connect(gainNode); gainNode.connect(ctx.destination);
  }catch(err){
    console.warn('降级录音初始化失败:',err);
    releaseCapture(false); resetVoiceUI(); showVoiceError('录音初始化失败，请直接输入文字');
  }
}
function finalizeRecording(){
  DOM.voiceHint.textContent='正在识别...';
  if(!recChunks.length){
    pcmSamples=[]; resetVoiceUI(); showToast('没有听到声音，请再说一次'); return;
  }
  var blob=new Blob(recChunks,{type:recChunks[0]&&recChunks[0].type||'audio/webm'});
  recChunks=[];
  var tmpCtx=new(window.AudioContext||window.webkitAudioContext)();
  var fr=new FileReader();
  fr.onload=function(){
    tmpCtx.decodeAudioData(fr.result, function(buf){
      var wav=encodeBufferToWav(buf,TARGET_RATE);
      sendToASR(wav);
      try{tmpCtx.close();}catch(e){}
    }, function(){
      try{tmpCtx.close();}catch(e){}
      pcmSamples=[]; resetVoiceUI(); showToast('音频解码失败，请重试');
    });
  };
  fr.readAsArrayBuffer(blob);
}
function encodeBufferToWav(audioBuffer, targetRate){
  var inputRate=audioBuffer.sampleRate, src=audioBuffer.getChannelData(0);
  var ratio=inputRate/targetRate, outLen=Math.ceil(src.length/ratio);
  var pcm=new Int16Array(outLen);
  for(var i=0;i<outLen;i++){
    var s=src[Math.floor(i*ratio)];
    s=Math.max(-1,Math.min(1,s));
    pcm[i]=s<0?s*0x8000:s*0x7FFF;
  }
  var buffer=new ArrayBuffer(44+pcm.length*2), view=new DataView(buffer);
  function writeStr(offset,str){ for(var k=0;k<str.length;k++) view.setUint8(offset+k,str.charCodeAt(k)); }
  writeStr(0,'RIFF'); view.setUint32(4,36+pcm.length*2,true); writeStr(8,'WAVE');
  writeStr(12,'fmt '); view.setUint32(16,16,true); view.setUint16(20,1,true); view.setUint16(22,1,true);
  view.setUint32(24,targetRate,true); view.setUint32(28,targetRate*2,true); view.setUint16(32,2,true); view.setUint16(34,16,true);
  writeStr(36,'data'); view.setUint32(40,pcm.length*2,true);
  for(var i=0;i<pcm.length;i++) view.setInt16(44+i*2,pcm[i],true);
  return new Blob([buffer],{type:'audio/wav'});
}
function releaseCapture(keepStream){
  isRecording=false;
  if(mediaRecorder&&mediaRecorder.state!=='inactive'){ try{mediaRecorder.stop();}catch(e){} }
  mediaRecorder=null;
  if(processorNode){ try{processorNode.disconnect();}catch(e){} processorNode=null; }
  if(sourceNode){ try{sourceNode.disconnect();}catch(e){} sourceNode=null; }
  if(gainNode){ try{gainNode.disconnect();}catch(e){} gainNode=null; }
  // keepStream=true：保留媒体流供下次复用，避免重复弹权限询问；离开页面时 false 彻底释放
  if(!keepStream&&mediaStream){ mediaStream.getTracks().forEach(function(t){t.stop();}); mediaStream=null; }
}
function encodeWav(samples, sampleRate){
  var buffer=new ArrayBuffer(44+samples.length*2), view=new DataView(buffer);
  function writeStr(offset,str){ for(var i=0;i<str.length;i++) view.setUint8(offset+i,str.charCodeAt(i)); }
  writeStr(0,'RIFF'); view.setUint32(4,36+samples.length*2,true); writeStr(8,'WAVE');
  writeStr(12,'fmt '); view.setUint32(16,16,true); view.setUint16(20,1,true); view.setUint16(22,1,true);
  view.setUint32(24,sampleRate,true); view.setUint32(28,sampleRate*2,true); view.setUint16(32,2,true); view.setUint16(34,16,true);
  writeStr(36,'data'); view.setUint32(40,samples.length*2,true);
  for(var i=0;i<samples.length;i++) view.setInt16(44+i*2,samples[i],true);
  return new Blob([buffer],{type:'audio/wav'});
}
async function sendToASR(wavBlob){
  var r=await API.transcribeAudio(wavBlob);
  DOM.voiceHint.textContent='按住说话';
  if(r.error){
    if(r.error.code==='NETWORK_ERROR') showToast('后端未连接，无法语音识别，请直接输入文字');
    else showToast(r.error.message||'语音识别失败，请直接输入文字');
    return;
  }
  var text=r.data&&r.data.text;
  if(text&&text.trim()){ submit(text.trim()); }
  else{ showToast('没有听清，请再说一次'); }
}
function resetVoiceUI(){
  DOM.voiceBtn.classList.remove('recording','pressing');
  DOM.voiceHint.textContent='按住说话';
  DOM.voiceHint.classList.remove('listening');
}
function pressVoice(){
  if(isRecording) return;
  if(voicePermDenied){ showVoiceError('麦克风权限已被拒绝，请到浏览器地址栏允许麦克风后重试，或直接输入文字。'); return; }
  isRecording=true;
  DOM.voiceBtn.classList.add('recording','pressing');
  DOM.voiceHint.textContent='正在听，松开发送...'; DOM.voiceHint.classList.add('listening');
  startCapture();
  if(voiceMaxTimer) clearTimeout(voiceMaxTimer);
  voiceMaxTimer=setTimeout(function(){ if(isRecording) releaseVoice(); }, MAX_RECORD_MS);
}
function releaseVoice(){
  if(!isRecording) return;
  if(voiceMaxTimer){ clearTimeout(voiceMaxTimer); voiceMaxTimer=null; }
  DOM.voiceBtn.classList.remove('pressing');
  DOM.voiceHint.textContent='正在识别...';
  var mode=captureMode;
  releaseCapture(true); // 保留媒体流，供下次按住说话复用，不再重复弹权限询问
  if(mode==='recorder') return; // onstop → finalizeRecording 继续处理
  // ScriptProcessor 降级路径
  if(pcmSamples.length<1600){ // 不足 0.1 秒视为未说话
    pcmSamples=[]; resetVoiceUI(); showToast('没有听到声音，请再说一次'); return;
  }
  var wavBlob=encodeWav(pcmSamples,TARGET_RATE);
  pcmSamples=[];
  sendToASR(wavBlob);
}

function submit(text){
  if(!text||!text.trim()){ showToast('请先说出或输入您的需求'); return; }
  text=text.trim();
  localStorage.setItem('lastMealQuery', text); // 记住上次输入，供“再来一份”检索相关餐食
  sessionStorage.setItem('userQuery',text);
  PageManager.navigate('thinking');
}
async function checkRecentOrder(){
  var r=await API.getFamilyOrders();
  if(!r.error&&Array.isArray(r.data)&&r.data.length>0){
    recentOrder=r.data[0];
  }else{
    // 后端暂无订单（如服务重启清空内存）时，回退到本地记录的上次下单餐食
    var saved=localStorage.getItem('lastOrderMeal');
    recentOrder=null;
    if(saved){ try{ recentOrder=JSON.parse(saved); }catch(e){ recentOrder=null; } }
  }
  if(recentOrder&&recentOrder.meal_name){
    DOM.reorderBtn.classList.remove('quick-card--hidden');
    DOM.reorderDesc.textContent='上次的「'+recentOrder.meal_name+'」';
  }
}
async function handleTodayRecommend(){
  var h=new Date().getHours(), q='今日推荐';
  if(h>=6&&h<10) q='来一份营养早餐'; else if(h>=10&&h<14) q='来一份午餐，清淡管饱'; else if(h>=14&&h<17) q='下午来点小食'; else q='来一份热乎的晚餐';
  sessionStorage.setItem('userQuery',q);
  sessionStorage.setItem('todayMode','1'); // 标记走“今日推荐”大模型三维度推荐
  PageManager.navigate('thinking');
}
function handleReorder(){
  if(!recentOrder){ showToast('还没有历史订单哦'); return; }
  var mid=recentOrder.meal_id;
  if(!mid){ showToast('暂无法获取上次的餐食'); return; }
  // 直接进入推荐结果页，优先展示上次下单的餐食
  sessionStorage.setItem('reorderMealId', mid);
  sessionStorage.setItem('reorderMode','1');
  sessionStorage.setItem('userQuery','再来一份');
  PageManager.navigate('recommend');
}

// Page hooks
PageManager.pageHooks.home = {
  onEnter: function(){
    setGreeting(); setWeather(); checkRecentOrder();
  },
  onLeave: function(){
    // 离开首页时中止未完成的录音，避免资源泄漏
    if(isRecording){
      if(voiceMaxTimer){ clearTimeout(voiceMaxTimer); voiceMaxTimer=null; }
      releaseCapture(false); pcmSamples=[]; resetVoiceUI();
    }
  }
};

function bindEvents(){
  // 按住说话：按下开始录音，松开结束并调用大模型 ASR 识别
  // 按住说话：按下开始录音，松开（任意位置）结束并调用大模型 ASR 识别
  // 松开事件挂在 document 上，避免手指/鼠标移出按钮（或按钮缩小）导致录音丢失
  DOM.voiceBtn.addEventListener('mousedown',function(e){ e.preventDefault(); pressVoice(); });
  DOM.voiceBtn.addEventListener('touchstart',function(e){ e.preventDefault(); pressVoice(); },{passive:false});
  document.addEventListener('mouseup',function(){ if(isRecording) releaseVoice(); });
  document.addEventListener('touchend',function(){ if(isRecording) releaseVoice(); },{passive:false});
  document.addEventListener('touchcancel',function(){ if(isRecording) releaseVoice(); },{passive:false});
  // Text input
  DOM.sendTextBtn.addEventListener('click',function(){
    var t=DOM.textInput.value.trim(); if(t){ submit(t); DOM.textInput.value=''; } else showToast('请输入您的需求');
  });
  DOM.textInput.addEventListener('keypress',function(e){ if(e.key==='Enter'){ e.preventDefault(); DOM.sendTextBtn.click(); } });
  // Quick actions
  DOM.todayRecommend.addEventListener('click',handleTodayRecommend);
  DOM.reorderBtn.addEventListener('click',handleReorder);
  // Bottom nav
  document.querySelectorAll('#page-home .nav-item').forEach(function(item){
    item.addEventListener('click',function(){
      var page=item.getAttribute('data-page');
      if(page==='orders') PageManager.navigate('orders');
      else if(page==='profile') PageManager.navigate('profile');
    });
  });
}

function init(){
  DOM.greetingTitle=document.getElementById('greetingTitle');
  DOM.weatherIcon=document.getElementById('weatherIcon'); DOM.weatherTemp=document.getElementById('weatherTemp');
  DOM.weatherDesc=document.getElementById('weatherDesc'); DOM.weatherDate=document.getElementById('weatherDate');
  DOM.voiceBtn=document.getElementById('voiceBtn'); DOM.voiceBtnRing=document.getElementById('voiceBtnRing');
  DOM.voiceHint=document.getElementById('voiceHint'); DOM.voiceFallback=document.getElementById('voiceFallback');
  DOM.textInput=document.getElementById('textInput'); DOM.sendTextBtn=document.getElementById('sendTextBtn');
  DOM.todayRecommend=document.getElementById('todayRecommend'); DOM.reorderBtn=document.getElementById('reorderBtn');
  DOM.reorderDesc=document.getElementById('reorderDesc');
  // 语音错误弹窗关闭
  var errClose=document.getElementById('voiceErrorClose');
  if(errClose) errClose.addEventListener('click',hideVoiceError);
  var errOverlay=document.getElementById('voiceErrorOverlay');
  if(errOverlay) errOverlay.addEventListener('click',function(e){ if(e.target===this) hideVoiceError(); });
  bindEvents(); setGreeting(); setWeather();
  API.healthCheck().then(function(ok){ if(!ok) showToast('离线模式 · 请启动后端服务以体验完整功能'); });
  checkRecentOrder();
}
init();
})();

// ================================================================
// PAGE 02: AI 思考中（大模型工作流实时进度：SSE 流式）
// ================================================================
(function(){
var DOM={}, currentStep=0, cancelled=false, completed=false, userQuery='', controller=null, timeoutTimer=null;

function setStepState(idx,state){
  var step=DOM.steps[idx]; if(!step) return;
  step.classList.remove('timeline-step--pending','timeline-step--active','timeline-step--done','timeline-step--error');
  step.classList.add('timeline-step--'+state);
  if(state==='active'||state==='pending'){ var d=step.querySelector('.step-desc'); if(d) d.textContent=d.getAttribute('data-default'); }
}
function resetAllSteps(){
  DOM.steps.forEach(function(s,i){ setStepState(i,'pending'); });
  currentStep=0; setStepState(0,'active');
}
function updateStepDesc(idx,msg){
  var step=DOM.steps[idx]; if(!step) return;
  var d=step.querySelector('.step-desc'); if(!d) return;
  d.style.opacity='0'; setTimeout(function(){ d.textContent=msg; d.style.opacity='1'; },150);
}
function getGeoPos(){
  return new Promise(function(resolve){
    if(!navigator.geolocation){ resolve(null); return; }
    navigator.geolocation.getCurrentPosition(resolve,function(){resolve(null);},{timeout:4000,maximumAge:600000});
  });
}

// 处理工作流事件：按步骤实时打勾并推进
function handleWorkflowEvent(ev){
  if(cancelled) return;
  var idx=(ev.step||1)-1;
  if(idx<0||idx>=4) return;
  if(ev.status==='running'){
    setStepState(idx,'active');
    updateStepDesc(idx,ev.detail||'');
  }else if(ev.status==='done'){
    setStepState(idx,'done');
    updateStepDesc(idx,ev.detail||'');
    if(idx+1<4) setStepState(idx+1,'active');
    if(ev.result){
      completed=true;
      ev.result.meals=(ev.result.meals||[]).map(ensureMealImage);
      sessionStorage.setItem('recommendResult',JSON.stringify(ev.result));
      sessionStorage.setItem('userQuery',userQuery);
      DOM.thinkingDots.style.display='none';
      if(timeoutTimer) clearTimeout(timeoutTimer);
      setTimeout(function(){ if(!cancelled) PageManager.navigate('recommend'); },700);
    }
  }else if(ev.status==='error'){
    setStepState(idx,'error');
    updateStepDesc(idx,ev.detail||'');
    DOM.thinkingDots.style.display='none';
    if(timeoutTimer) clearTimeout(timeoutTimer);
    if(idx===3){
      showToast('没有合适的餐品，请放宽条件后重试','error');
      setTimeout(function(){ if(!cancelled) PageManager.navigate('home'); },1800);
    }
  }
}

// SSE 流式读取后端工作流
async function runWorkflow(){
  var isToday=sessionStorage.getItem('todayMode')==='1';
  sessionStorage.removeItem('todayMode');
  var body={ text_input:userQuery, family_id:'family_001', elder_id:'elder_001', mode:isToday?'today':'input' };
  if(isToday){
    var pos=await getGeoPos();
    body.lat=pos&&pos.coords?pos.coords.latitude:null;
    body.lon=pos&&pos.coords?pos.coords.longitude:null;
  }
  try{
    var resp=await fetch(API.BASE_URL+'/api/meals/recommend/stream',{
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify(body), signal:controller?controller.signal:undefined
    });
    if(!resp.ok||!resp.body) throw new Error('stream unavailable');
    var reader=resp.body.getReader(), decoder=new TextDecoder(), buffer='';
    while(true){
      var chunk=await reader.read();
      if(chunk.done) break;
      buffer+=decoder.decode(chunk.value,{stream:true});
      var parts=buffer.split('\n\n'); buffer=parts.pop();
      parts.forEach(function(block){
        var line=null;
        block.split('\n').forEach(function(l){ if(l.indexOf('data:')===0) line=l; });
        if(line){
          try{ handleWorkflowEvent(JSON.parse(line.slice(5).trim())); }catch(e){ console.warn('SSE解析失败',e); }
        }
      });
    }
  }catch(e){
    if(!cancelled) showTimeoutFallback();
  }
}

function showTimeoutFallback(){
  if(cancelled||completed) return;  // 方案已生成或已取消则不显示超时提示
  DOM.timeoutFallback.style.display='flex';
  DOM.thinkingDots.style.display='none';
}
async function handleFallback(){
  cancelled=true;
  if(controller){ try{controller.abort();}catch(e){} controller=null; }
  if(timeoutTimer) clearTimeout(timeoutTimer);
  DOM.timeoutFallback.style.display='none';
  // 本地传统检索（不调用大模型）：按用户输入 + 家属规则过滤排序，取评分前三
  var q=sessionStorage.getItem('userQuery')||userQuery||'';
  DOM.thinkingDots.style.display='none';
  showToast('正在使用本地检索为您推荐...');
  var r=await API.recommendLocal(q);
  if(!r.error&&r.data){
    sessionStorage.setItem('recommendResult',JSON.stringify(r.data));
    sessionStorage.setItem('userQuery',q);
    setTimeout(function(){ PageManager.navigate('recommend'); },300);
  }else{
    // 后端断开：本地推荐也不可用，明确提示并回首页，不进入推荐页
    showToast((r.error&&r.error.code==='NETWORK_ERROR')?'服务器已断开，请重试':(r.error&&r.error.message||'推荐失败，请重试'),'error');
    setTimeout(function(){ PageManager.navigate('home'); },800);
  }
}

function setBottomHint(){
  var h=new Date().getHours(), meal;
  if(h>=5&&h<10) meal='早餐';
  else if(h>=10&&h<14) meal='午餐';
  else if(h>=14&&h<17) meal='下午茶';
  else if(h>=17&&h<21) meal='晚餐';
  else meal='一顿饭';
  if(DOM.bottomHintText) DOM.bottomHintText.textContent='马上就好，正在为您找到合适的'+meal+'！';
}

PageManager.pageHooks.thinking = {
  onEnter: function(){
    userQuery=sessionStorage.getItem('userQuery')||'';
    cancelled=false; completed=false;
    controller=new AbortController();
    resetAllSteps();
    setBottomHint(); // 按本地实时时间判定早/午/晚餐
    DOM.thinkingDots.style.display='flex';
    DOM.timeoutFallback.style.display='none';
    if(timeoutTimer) clearTimeout(timeoutTimer);
    // 15 秒内大模型未完成 → 显示“用本地推荐继续”备选按钮
    timeoutTimer=setTimeout(function(){ if(!cancelled) showTimeoutFallback(); },15000);
    runWorkflow();
  },
  onLeave: function(){
    cancelled=true; completed=false;
    if(timeoutTimer) clearTimeout(timeoutTimer);
    if(controller){ try{controller.abort();}catch(e){} controller=null; }
  }
};

function init(){
  DOM.steps=document.querySelectorAll('#page-thinking .timeline-step');
  DOM.thinkingDots=document.getElementById('thinkingDots');
  DOM.timeoutFallback=document.getElementById('timeoutFallback');
  DOM.bottomHintText=document.getElementById('bottomHintText');
  document.getElementById('fallbackBtn').addEventListener('click',handleFallback);
}
init();
})();

// ================================================================
// PAGE 03: 推荐结果
// ================================================================
(function(){
var DOM={}, meals=[], reasons=[], currentMealIdx=0, querySummary='', isOrdering=false;
var TAG_LABELS={
  low_oil:'低油',low_salt:'低盐',low_sugar:'低糖',soft_food:'软烂易消化',
  vegetarian:'素食',high_protein:'高蛋白',low_carb:'低碳水',gluten_free:'无麸质',
  halal:'清真',no_pork:'无猪肉',no_seafood:'无海鲜',low_purine:'低嘌呤'
};

function genReasons(meal,limit){ limit=limit||30; var rs=[],tags=meal.dietary_tags||[];
  if(tags.includes('low_oil')) rs.push('符合您设定的低油偏好');
  if(tags.includes('low_salt')) rs.push('符合家属设定的低盐规则');
  if(tags.includes('low_sugar')) rs.push('低糖健康，适合日常饮食');
  if(tags.includes('soft_food')) rs.push('口感软烂，易于咀嚼消化');
  if(tags.includes('vegetarian')) rs.push('素食餐，不含肉食和海鲜');
  if(tags.includes('high_protein')) rs.push('高蛋白，有助于补充营养');
  if(tags.includes('low_carb')) rs.push('低碳水，适合控糖控主食');
  if(tags.includes('gluten_free')) rs.push('无麸质，减少面筋摄入');
  if(tags.includes('halal')) rs.push('清真餐，无猪肉');
  if(tags.includes('no_pork')) rs.push('不含猪肉');
  if(tags.includes('no_seafood')) rs.push('不含海鲜');
  if(tags.includes('low_purine')) rs.push('低嘌呤，适合尿酸偏高人群');
  if(meal.price<=limit) rs.push('价格 ¥'+meal.price.toFixed(2)+'，在 '+limit+' 元预算内');
  var h=new Date().getHours(); if(h>=10&&h<14) rs.push('午餐时段，为您选择营养均衡的餐品');
  if(meal.calories&&meal.calories<400) rs.push('热量适中（'+meal.calories+'千卡），轻松无负担');
  if(rs.length<3){ rs.push('根据您的口味偏好精心挑选'); rs.push('综合评分最高，值得推荐'); }
  return rs.slice(0,5);
}
function renderMeal(idx){
  if(idx>=meals.length) return;
  var m=ensureMealImage(meals[idx]), rs=(Array.isArray(reasons[idx])&&reasons[idx].length)?reasons[idx]:genReasons(m);
  DOM.mealName.textContent=m.name||'推荐餐品'; DOM.mealDesc.textContent=m.description||'';
  DOM.mealPrice.textContent=Math.floor(m.price||0); DOM.mealEta.textContent=m.eta_minutes||'--';
  // Tags
  DOM.mealTags.innerHTML=''; var tags=m.dietary_tags||[];
  if(!tags.length||(tags.length===1&&tags[0]==='none')){
    var dt=document.createElement('span'); dt.className='meal-tag'; dt.textContent='精选'; DOM.mealTags.appendChild(dt);
  }else{
    tags.forEach(function(t){ var l=TAG_LABELS[t]||t; if(l){ var el=document.createElement('span'); el.className='meal-tag'; el.textContent=l; DOM.mealTags.appendChild(el); } });
  }
  // Image（带版本号，避免浏览器缓存旧餐品图片）
  if(m.image_url){ DOM.mealImage.onerror=function(){ DOM.mealImage.style.display='none'; var p=DOM.mealImageArea.querySelector('.meal-placeholder'); if(p) p.style.display='flex'; }; DOM.mealImage.src=m.image_url+(m.image_url.indexOf('?')>=0?'&':'?')+'v=20260802'; DOM.mealImage.style.display='block'; var ph=DOM.mealImageArea.querySelector('.meal-placeholder'); if(ph) ph.style.display='none'; }
  else{ DOM.mealImage.style.display='none'; var ph=DOM.mealImageArea.querySelector('.meal-placeholder'); if(ph) ph.style.display='flex'; }
  // Reasons
  DOM.reasonList.innerHTML=''; rs.forEach(function(r){ var li=document.createElement('li'); li.className='reason-item'; li.innerHTML='<span class="reason-icon">✓</span><span class="reason-text">'+r+'</span>'; DOM.reasonList.appendChild(li); });
  DOM.swapBtn.disabled=meals.length<=1;
}
function loadData(){
  var saved=sessionStorage.getItem('recommendResult'), uq=sessionStorage.getItem('userQuery')||''; querySummary=uq;
  if(saved){ try{
    var d=JSON.parse(saved); if(d.meals&&d.meals.length>0){ meals=d.meals.map(ensureMealImage);
      if(d.reasons&&Array.isArray(d.reasons)){
        if(Array.isArray(d.reasons[0])) reasons=d.reasons;
        // 后端 reasons 是每餐一个字符串（'；'分隔），拆分为数组便于逐条展示
        else reasons=d.reasons.map(function(s){return String(s||'').split('；').filter(Boolean);});
      }
      else reasons=d.meals.map(function(m){return genReasons(m);});
      querySummary=d.query_summary||uq; return true;
    }
  }catch(e){console.warn('解析推荐数据失败');} }
  // 无推荐数据（后端断开等）：不退回硬编码假餐食，由 onEnter 提示并回首页
  return false;
}
async function handleOrder(){
  if(isOrdering||currentMealIdx>=meals.length) return; isOrdering=true;
  var m=meals[currentMealIdx];
  DOM.orderBtn.classList.add('loading'); DOM.orderBtn.innerHTML='<span class="cta-loading-dots"><span></span><span></span><span></span></span>';
  DOM.swapBtn.disabled=true;
  var r=await API.createOrder(m.id);
  if(r.error){
    isOrdering=false; DOM.orderBtn.classList.remove('loading'); DOM.orderBtn.innerHTML='<span class="cta-text">就吃这个</span>'; DOM.swapBtn.disabled=meals.length<=1;
    // 断网/失败一律明确报错，不创建假定单、不进入配送流程
    showToast(r.error.code==='NETWORK_ERROR'?'网络异常，下单失败，请重试':(r.error.message||'下单失败，请重试'),'error');
    return;
  }
  showToast('下单成功！正在为您准备...','success');
  var od=r.data||{}, oid=od.order_id||'ORD-'+Date.now();
  // 记录最近下单餐食（含 meal_id），供“再来一份”在后端无订单时兜底显示
  localStorage.setItem('lastOrderMeal',JSON.stringify({meal_id:m.id,meal_name:m.name,meal_price:m.price}));
  sessionStorage.setItem('currentOrder',JSON.stringify({order_id:oid,status:od.status||'created',meal_name:m.name,meal_price:m.price,meal_id:m.id,image_url:m.image_url||'',eta_minutes:m.eta_minutes||od.eta_minutes||35,created_at:od.created_at||new Date().toISOString()}));
  setTimeout(function(){goDelivery(oid,m);},600);
}
function goDelivery(oid,m){ PageManager.navigate('delivery'); }
function handleSwap(){ if(meals.length<=1) return; currentMealIdx=(currentMealIdx+1)%meals.length; renderMeal(currentMealIdx); window.scrollTo({top:0,behavior:'smooth'}); showToast('已为您更换推荐 ('+(currentMealIdx+1)+'/'+meals.length+')'); }

async function loadReorder(){
  var mid=sessionStorage.getItem('reorderMealId');
  var lastQuery=localStorage.getItem('lastMealQuery')||'';
  sessionStorage.removeItem('reorderMode');
  sessionStorage.removeItem('reorderMealId');
  querySummary='您说：再来一份，请稍等...';
  DOM.queryText.textContent=querySummary;
  meals=[]; reasons=[];
  // 1. 上次下单的餐食优先
  var reorderMeal=null;
  if(mid){
    var r1=await API.getMealById(mid);
    if(!r1.error&&r1.data) reorderMeal=r1.data;
  }
  // 2. 大模型按上次输入检索两份相关餐食
  var related=[];
  if(lastQuery){
    var r2=await API.recommendMeals(lastQuery);
    if(!r2.error&&r2.data&&Array.isArray(r2.data.meals)) related=r2.data.meals;
  }
  if(!related.length){
    var r3=await API.recommendMeals('再来一份，清淡管饱');
    if(!r3.error&&r3.data&&Array.isArray(r3.data.meals)) related=r3.data.meals;
  }
  // 3. 组合去重：上次下单 + 相关，最多 3 份
  var seen={};
  if(reorderMeal){ meals.push(reorderMeal); seen[reorderMeal.id]=1; }
  (related||[]).forEach(function(m){
    if(meals.length>=3) return;
    if(!seen[m.id]){ meals.push(m); seen[m.id]=1; }
  });
  if(!meals.length){
    // 后端断开/无数据：不退回硬编码假餐食，明确提示并回首页
    showToast('服务器已断开，无法获取推荐，请重试','error');
    setTimeout(function(){ PageManager.navigate('home'); },800);
    return;
  }
  reasons=meals.map(function(m){
    return (reorderMeal&&m.id===reorderMeal.id)?['您上次点过这份，为您再次下单']:[];
  });
  renderMeal(0);
  // 大模型响应完成，恢复“就吃这个”按钮
  DOM.orderBtn.disabled=false;
  DOM.orderBtn.classList.remove('loading');
  DOM.orderBtn.innerHTML='<span class="cta-text">就吃这个</span>';
}

PageManager.pageHooks.recommend = {
  onEnter: function(){
    isOrdering=false; currentMealIdx=0;
    if(sessionStorage.getItem('reorderMode')==='1'){
      // 大模型检索期间禁用“就吃这个”按钮，避免点击无响应
      DOM.orderBtn.disabled=true;
      DOM.orderBtn.classList.add('loading');
      DOM.orderBtn.innerHTML='<span class="cta-loading-dots"><span></span><span></span><span></span></span>';
      loadReorder();
      return;
    }
    DOM.orderBtn.disabled=false;
    DOM.orderBtn.classList.remove('loading'); DOM.orderBtn.innerHTML='<span class="cta-text">就吃这个</span>';
    if(!loadData()){
      // 无推荐数据（后端断开等）：明确提示并回首页
      showToast('服务器已断开，无法获取推荐，请重试','error');
      setTimeout(function(){ PageManager.navigate('home'); },800);
      return;
    }
    DOM.queryText.textContent=querySummary||'为您找到以下推荐';
    renderMeal(0);
  }
};

function init(){
  DOM.queryText=document.getElementById('queryText'); DOM.mealTags=document.getElementById('mealTags');
  DOM.mealImage=document.getElementById('mealImage'); DOM.mealImageArea=document.getElementById('mealImageArea');
  DOM.mealName=document.getElementById('mealName'); DOM.mealDesc=document.getElementById('mealDesc');
  DOM.mealPrice=document.getElementById('mealPrice'); DOM.mealEta=document.getElementById('mealEta');
  DOM.reasonList=document.getElementById('reasonList'); DOM.orderBtn=document.getElementById('orderBtn');
  DOM.swapBtn=document.getElementById('swapBtn');
  DOM.orderBtn.addEventListener('click',handleOrder); DOM.swapBtn.addEventListener('click',handleSwap);
}
init();
})();

// ================================================================
// PAGE 04: 订单配送中
// ================================================================
(function(){
var DOM={}, STATUS_ORDER=['created','paid','preparing','delivering','delivered'];
var STATUS_INFO={
  created:{title:'订单已创建',subtitle:'商家已收到您的订单，即将开始制作',tip:'订单已成功提交～商家接单后会立即为您制作。',etaPrefix:'预计',etaSuffix:'后送达'},
  preparing:{title:'商家正在制作中',subtitle:'您的午餐正在精心准备，请稍等片刻',tip:'餐品正在制作中，请耐心等待～制作完成后骑手会立即取餐配送。',etaPrefix:'约',etaSuffix:'后送达'},
  delivering:{title:'骑手配送中',subtitle:'骑手已取餐，正在为您配送的路上',tip:'骑手正在赶来的路上🚀 请保持电话畅通，留意门铃哦～',etaPrefix:'约',etaSuffix:'后到达'},
  delivered:{title:'餐品已送达',subtitle:'您的餐品已送到，请查收',tip:'餐品已送达！请确认收到餐品后点击收餐～',etaPrefix:'',etaSuffix:''},
};
var HEADER_TITLES={
  created:'订单下单中', paid:'订单下单中', preparing:'订单制作中',
  delivering:'订单配送中', delivered:'订单已送达',
};
var currentStatus='preparing', orderId='', orderData=null, etaMinutes=35, pollingTimer=null, countdownTimer=null, isAdvancing=false, deliveryNavTimer=null;

function updateScene(s){
  // 状态窗口已改为展示餐品实拍图 + 状态文字，不再使用 SVG 场景
}
function updateStatusInfo(s){
  var info=STATUS_INFO[s]||STATUS_INFO['preparing'];
  DOM.statusTitle.textContent=info.title; DOM.statusSubtitle.textContent=info.subtitle; DOM.tipText.textContent=info.tip;
  // 顶部标题随订单状态实时更新
  if(DOM.deliveryTitle) DOM.deliveryTitle.textContent=HEADER_TITLES[s]||HEADER_TITLES['preparing'];
  if(s==='delivered'){ DOM.etaTime.textContent='已送达'; DOM.etaCountdown.textContent='请确认收餐'; }
  else{ DOM.etaTime.textContent=info.etaPrefix+' '+etaMinutes+' 分钟'+info.etaSuffix; DOM.etaCountdown.textContent='正在更新中...'; }
}
function updateProgress(s){
  var steps=document.querySelectorAll('#page-delivery .progress-step'), lines=document.querySelectorAll('#page-delivery .progress-line'), found=false;
  steps.forEach(function(step,i){
    var ss=step.getAttribute('data-status'); step.classList.remove('progress-step--done','progress-step--active');
    if(ss===s){ step.classList.add('progress-step--active'); found=true; } else if(!found) step.classList.add('progress-step--done');
  });
  lines.forEach(function(line,i){
    var prev=steps[i], next=steps[i+1]; line.classList.remove('progress-line--done','progress-line--active');
    if(prev&&prev.classList.contains('progress-step--done')) line.classList.add('progress-line--done');
    else if(prev&&prev.classList.contains('progress-step--active')) line.classList.add('progress-line--active');
  });
}
function syncUI(s){ updateScene(s); updateStatusInfo(s); updateProgress(s); currentStatus=s; }
function advanceStatus(){
  var idx=STATUS_ORDER.indexOf(currentStatus); if(idx<0||idx>=STATUS_ORDER.length-1) return;
  var ns=STATUS_ORDER[idx+1]; syncUI(ns);
  if(ns==='delivering'){ etaMinutes=Math.max(5,etaMinutes-15); updateStatusInfo(ns); }
  else if(ns==='delivered'){
    etaMinutes=0; DOM.etaTime.textContent='已送达'; DOM.etaCountdown.textContent='请确认收餐';
    DOM.advanceBtn.disabled=true; DOM.advanceBtn.textContent='✓ 已送达';
    if(deliveryNavTimer)clearTimeout(deliveryNavTimer);deliveryNavTimer=setTimeout(function(){PageManager.navigate('receipt');},2000);
  }
  return ns;
}
async function handleAdvance(){
  if(isAdvancing) return; isAdvancing=true;
  var isSim=orderId.indexOf('OFFLINE')!==-1||orderId.indexOf('DEMO')!==-1;
  if(isSim){
    // 模拟/演示订单：本地推进状态（离线演示路径）
    var nx=advanceStatus();
    if(nx==='delivered') showToast('餐品已送达！正在进入收餐确认...','success');
    else if(nx) showToast('状态已更新：'+(STATUS_INFO[nx]?STATUS_INFO[nx].title:nx));
    isAdvancing=false;
    return;
  }
  if(!orderId){ showToast('暂无订单'); isAdvancing=false; return; }
  var r=currentStatus==='delivering'?await API.deliverOrder(orderId):await API.advanceOrder(orderId);
  if(r.error){
    // 真实订单断网/失败 → 明确报错，不本地模拟状态
    showToast(r.error.code==='NETWORK_ERROR'?'网络异常，状态更新失败，请重试':(r.error.message||'状态更新失败，请重试'),'error');
    isAdvancing=false;
    return;
  }
  var ns=r.data&&r.data.status;
  if(ns&&ns!==currentStatus){
    syncUI(ns);
    if(ns==='delivered'){ etaMinutes=0; DOM.etaTime.textContent='已送达'; DOM.etaCountdown.textContent='请确认收餐'; DOM.advanceBtn.disabled=true; DOM.advanceBtn.textContent='✓ 已送达';
      showToast('餐品已送达！','success'); if(deliveryNavTimer)clearTimeout(deliveryNavTimer);deliveryNavTimer=setTimeout(function(){PageManager.navigate('receipt');},2000); }
  }
  isAdvancing=false;
}
function loadOrderData(){
  var saved=sessionStorage.getItem('currentOrder');
  if(saved){ try{ orderData=JSON.parse(saved); orderId=orderData.order_id||''; currentStatus=orderData.status||'preparing'; etaMinutes=orderData.eta_minutes||35; }catch(e){} }
  if(!orderData) return false;   // 无订单信息时不创建假定单，由 onEnter 引导回首页
  if(currentStatus==='delivered'){ DOM.advanceBtn.disabled=true; DOM.advanceBtn.textContent='✓ 已送达'; }
  renderDeliveryMeal();
  return true;
}
function renderDeliveryMeal(){
  if(!orderData) return;
  if(DOM.deliveryMealName) DOM.deliveryMealName.textContent=orderData.meal_name||'正在为您准备餐品...';
  if(DOM.deliveryMealPrice) DOM.deliveryMealPrice.textContent='¥'+((orderData.meal_price||0).toFixed(2));
  if(DOM.deliveryMealImg) setMealImg(DOM.deliveryMealImg, DOM.deliveryMealPh, orderData.image_url);
  if(!orderData.image_url&&orderData.meal_id) fetchMealImage(orderData.meal_id, function(url){ orderData.image_url=url; if(DOM.deliveryMealImg) setMealImg(DOM.deliveryMealImg, DOM.deliveryMealPh, url); });
}
function startPolling(){
  if(pollingTimer) clearInterval(pollingTimer);
  if(orderId&&orderId.indexOf('OFFLINE')===-1&&orderId.indexOf('DEMO')===-1){
    pollingTimer=setInterval(async function(){
      var r=await API.getOrderStatus(orderId);
      if(!r.error&&r.data){ var rs=r.data.status; if(rs&&rs!==currentStatus){ syncUI(rs);
        if(rs==='delivered'){ if(pollingTimer)clearInterval(pollingTimer); DOM.advanceBtn.disabled=true; DOM.advanceBtn.textContent='✓ 已送达'; showToast('餐品已送达！','success'); if(deliveryNavTimer)clearTimeout(deliveryNavTimer);deliveryNavTimer=setTimeout(function(){PageManager.navigate('receipt');},2000); }
      } }
    },5000);
  }
}
function startCountdown(){
  if(countdownTimer) clearInterval(countdownTimer);
  var remaining=etaMinutes*60, startTime=Date.now();
  countdownTimer=setInterval(function(){
    if(currentStatus==='delivered'){clearInterval(countdownTimer);return;}
    var elapsed=Math.floor((Date.now()-startTime)/1000), left=Math.max(0,remaining-elapsed), mins=Math.floor(left/60), secs=left%60;
    DOM.etaCountdown.textContent=mins>0?'约 '+mins+' 分 '+secs+' 秒':'即将送达';
  },1000);
}

function handleCancelOrder(){
  if(!orderId){ showToast('暂无订单'); return; }
  // 弹出确认弹窗，由用户在弹窗内决定
  var overlay=document.getElementById('cancelConfirmOverlay');
  if(overlay) overlay.style.display='flex';
}
function hideCancelConfirm(){
  var overlay=document.getElementById('cancelConfirmOverlay');
  if(overlay) overlay.style.display='none';
}
function confirmCancelOrder(){
  hideCancelConfirm();
  var isReal=orderId.indexOf('OFFLINE')===-1&&orderId.indexOf('DEMO')===-1;
  if(!isReal){
    // 模拟/演示订单：直接模拟取消回首页
    showToast('已取消（演示订单）');
    PageManager.navigate('home');
    return;
  }
  API.cancelOrder(orderId).then(function(r){
    if(r.error){
      // 真实订单网络失败 → 明确报错，不假装成功
      showToast(r.error.code==='NETWORK_ERROR'?'网络异常，取消失败，请重试':(r.error.message||'取消失败，请重试'),'error');
    }else{
      showToast('订单已取消','success');
      PageManager.navigate('home');
    }
  });
}
function handleDeliveryHome(){ PageManager.navigate('home'); }

PageManager.pageHooks.delivery = {
  onEnter: function(){
    isAdvancing=false;
    if(!loadOrderData()){ showToast('暂无订单信息，请重新下单','error'); setTimeout(function(){ PageManager.navigate('home'); },800); return; }
    syncUI(currentStatus);
    if(currentStatus==='delivered'){ DOM.advanceBtn.disabled=true; DOM.advanceBtn.textContent='✓ 已送达'; }
    else{ DOM.advanceBtn.disabled=false; DOM.advanceBtn.textContent='推进状态（Demo）'; }
    hideCancelConfirm();
    startPolling(); startCountdown();
  },
  onLeave: function(){
    if(pollingTimer) clearInterval(pollingTimer); if(countdownTimer) clearInterval(countdownTimer);
    if(deliveryNavTimer) clearTimeout(deliveryNavTimer);
    hideCancelConfirm();
  }
};

function init(){
  DOM.statusTitle=document.getElementById('statusTitle'); DOM.statusSubtitle=document.getElementById('statusSubtitle');
  DOM.etaTime=document.getElementById('etaTime'); DOM.etaCountdown=document.getElementById('etaCountdown');
  DOM.advanceBtn=document.getElementById('advanceBtn'); DOM.tipText=document.getElementById('tipText');
  DOM.deliveryTitle=document.getElementById('deliveryTitle');
  DOM.cancelOrderBtn=document.getElementById('cancelOrderBtn'); DOM.deliveryHomeBtn=document.getElementById('deliveryHomeBtn');
  DOM.deliveryMealImg=document.getElementById('deliveryMealImg'); DOM.deliveryMealPh=document.getElementById('deliveryMealPh');
  DOM.deliveryMealName=document.getElementById('deliveryMealName'); DOM.deliveryMealPrice=document.getElementById('deliveryMealPrice');
  DOM.advanceBtn.addEventListener('click',handleAdvance);
  if(DOM.cancelOrderBtn) DOM.cancelOrderBtn.addEventListener('click',handleCancelOrder);
  if(DOM.deliveryHomeBtn) DOM.deliveryHomeBtn.addEventListener('click',handleDeliveryHome);
  // 取消确认弹窗
  var noBtn=document.getElementById('cancelNoBtn'); if(noBtn) noBtn.addEventListener('click',hideCancelConfirm);
  var yesBtn=document.getElementById('cancelYesBtn'); if(yesBtn) yesBtn.addEventListener('click',confirmCancelOrder);
  var overlay=document.getElementById('cancelConfirmOverlay');
  if(overlay) overlay.addEventListener('click',function(e){ if(e.target===this) hideCancelConfirm(); });
}
init();
})();

// ================================================================
// PAGE 05: 收餐确认
// ================================================================
(function(){
var DOM={}, orderData=null, isConfirming=false;

function loadOrderData(){
  var saved=sessionStorage.getItem('currentOrder');
  if(saved){ try{orderData=JSON.parse(saved);}catch(e){} }
  if(!orderData) return false;   // 无订单信息时不创建假定单，由 onEnter 引导回首页
  DOM.rctMealName.textContent=orderData.meal_name||'推荐餐品';
  DOM.rctMealPrice.textContent='¥'+((orderData.meal_price||0).toFixed(2));
  DOM.rctOrderId.textContent=orderData.order_id||'ORD-XXXXXXXX';
  setMealImg(DOM.rctMealImg, DOM.rctMealPh, orderData.image_url);
  if(!orderData.image_url&&orderData.meal_id) fetchMealImage(orderData.meal_id, function(url){ orderData.image_url=url; setMealImg(DOM.rctMealImg, DOM.rctMealPh, url); });
  return true;
}
function resetConfirmBtn(){
  isConfirming=false;
  DOM.confirmBtn.classList.remove('loading');
  DOM.confirmBtn.innerHTML='<span class="confirm-btn-text">我已收到</span>';
  DOM.contactBtn.disabled=false;
}
async function handleConfirm(){
  if(isConfirming) return; isConfirming=true;
  DOM.confirmBtn.classList.add('loading'); DOM.confirmBtn.innerHTML='<span class="confirm-loading-dots"><span></span><span></span><span></span></span>';
  DOM.contactBtn.disabled=true;
  var oid=(orderData&&orderData.order_id)||'';
  var isSim=(oid.indexOf('OFFLINE')!==-1||oid.indexOf('DEMO')!==-1);
  try{
    var r=isSim?{data:{status:'confirmed'},error:null}:await API.confirmReceipt(oid);
    // 真实订单网络失败 → 明确报错，不假装确认成功
    if(!isSim&&r.error){
      resetConfirmBtn();
      showToast(r.error.code==='NETWORK_ERROR'?'网络异常，确认失败，请重试':(r.error.message||'确认失败，请重试'),'error');
      return;
    }
  }catch(e){
    console.warn('确认异常:',e);
    resetConfirmBtn();
    showToast('确认失败，请重试','error');
    return;
  }
  if(orderData){ orderData.status='confirmed'; orderData.confirmed=true; orderData.confirmed_at=new Date().toISOString(); sessionStorage.setItem('currentOrder',JSON.stringify(orderData)); }
  // 成功：复位按钮并隐藏确认区，显示成功面板
  resetConfirmBtn();
  if(DOM.confirmArea) DOM.confirmArea.style.display='none';
  DOM.confirmSuccess.style.display='flex';
}
function handleContact(){ showToast('📞 已模拟联系骑手（Demo 功能，未实际拨打电话）'); }
function handleBackHome(){ PageManager.navigate('home'); }

PageManager.pageHooks.receipt = {
  onEnter: function(){
    resetConfirmBtn();
    if(DOM.confirmArea) DOM.confirmArea.style.display='';
    DOM.confirmSuccess.style.display='none';
    if(!loadOrderData()){ showToast('暂无订单信息，请重新下单','error'); setTimeout(function(){ PageManager.navigate('home'); },800); return; }
  }
};

function init(){
  DOM.rctMealName=document.getElementById('rctMealName'); DOM.rctMealPrice=document.getElementById('rctMealPrice');
  DOM.rctOrderId=document.getElementById('rctOrderId'); DOM.confirmBtn=document.getElementById('confirmBtn');
  DOM.contactBtn=document.getElementById('contactBtn'); DOM.confirmSuccess=document.getElementById('confirmSuccess');
  DOM.confirmArea=document.getElementById('confirmArea');
  DOM.rctMealImg=document.getElementById('rctMealImg'); DOM.rctMealPh=document.getElementById('rctMealPh');
  DOM.confirmBtn.addEventListener('click',handleConfirm); DOM.contactBtn.addEventListener('click',handleContact);
  document.getElementById('backHomeBtn').addEventListener('click',handleBackHome);
}
init();
})();

// ================================================================
// PAGE 06: 订单
// ================================================================
(function(){
var DOM={};

function statusLabel(s){
  var m={created:'已下单',paid:'已支付',preparing:'制作中',delivering:'配送中',delivered:'已送达',confirmed:'已收餐',cancelled:'已取消'};
  return m[s]||s;
}
function formatTime(iso){try{var d=new Date(iso);return d.getHours().toString().padStart(2,'0')+':'+d.getMinutes().toString().padStart(2,'0');}catch(e){return'--';}}

async function loadOrders(){
  var r=await API.getFamilyOrders();
  var orders=[];
  if(!r.error&&Array.isArray(r.data)) orders=r.data;
  // 也加入 sessionStorage 中的当前订单
  var saved=sessionStorage.getItem('currentOrder');
  if(saved){try{var co=JSON.parse(saved);if(!orders.find(function(o){return o.order_id===co.order_id;})) orders.unshift(co);}catch(e){}}
  renderOrders(orders);
}
function renderOrders(orders){
  DOM.ordersList.innerHTML='';
  if(!orders.length){ DOM.ordersEmpty.style.display='flex'; return; }
  DOM.ordersEmpty.style.display='none';
  var ACTIVE=['created','paid','preparing','delivering'];
  orders.forEach(function(o){
    var card=document.createElement('div'); card.className='order-history-card';
    var isActive=ACTIVE.indexOf(o.status)>=0||o.status==='delivered';
    card.innerHTML='<div class="ohc-top"><span class="ohc-meal">'+(o.meal_name||'餐品')+'</span><span class="ohc-status '+(isActive?'ohc-status--active':'ohc-status--done')+'">'+statusLabel(o.status)+'</span></div><div class="ohc-bottom"><span class="ohc-price">¥'+((o.meal_price||0).toFixed(2))+'</span><span class="ohc-time">'+formatTime(o.created_at||o.updated_at)+'</span></div>';
    card.addEventListener('click',function(){
      if(o.status==='delivered'){
        goToDelivery(o,'receipt');   // 已送达 → 订单实时状态（收餐确认）
      }else if(ACTIVE.indexOf(o.status)>=0){
        goToDelivery(o,'delivery');  // 进行中 → 订单实时页面
      }else{
        showOrderDetail(o);          // 已收餐/已取消 → 弹窗详情
      }
    });
    DOM.ordersList.appendChild(card);
  });
}
function goToDelivery(order,page){
  sessionStorage.setItem('currentOrder',JSON.stringify({
    order_id:order.order_id,
    status:order.status,
    meal_name:order.meal_name,
    meal_price:order.meal_price,
    meal_id:order.meal_id||'',
    image_url:order.image_url||'',
    eta_minutes:order.eta_minutes||35,
    created_at:order.created_at||new Date().toISOString()
  }));
  PageManager.navigate(page||'delivery');
}
function showOrderDetail(order){
  DOM.odModalMeal.textContent=order.meal_name||'--';
  DOM.odModalPrice.textContent='¥'+((order.meal_price||0).toFixed(2));
  DOM.odModalId.textContent=order.order_id||'--';
  var timeline=DOM.odModalTimeline;
  timeline.innerHTML='';
  var steps=[{key:'created',label:'已下单'},{key:'paid',label:'已支付'},{key:'preparing',label:'制作中'},{key:'delivering',label:'配送中'},{key:'delivered',label:'已送达'}];
  var stOrder=['created','paid','preparing','delivering','delivered'],curIdx=stOrder.indexOf(order.status);if(curIdx<0)curIdx=0;
  steps.forEach(function(s,i){
    var div=document.createElement('div'); div.className='mtl-step';
    var isDone=i<curIdx,isCur=i===curIdx;
    div.innerHTML='<div class="mtl-dot-wrap"><div class="mtl-dot'+(isDone?' mtl-dot--done':'')+(isCur?' mtl-dot--active':'')+'"></div><div class="mtl-line"></div></div><div class="mtl-info"><span class="mtl-title'+(isCur?' mtl-title--current':'')+'">'+s.label+'</span><span class="mtl-time">'+(isDone?formatTime(order.updated_at||order.created_at):(isCur&&order.status==='delivered'?'已到达':'--'))+'</span></div>';
    timeline.appendChild(div);
  });
  DOM.orderDetailModal.style.display='flex';
}
function hideModal(){ DOM.orderDetailModal.style.display='none'; }

PageManager.pageHooks.orders = { onEnter:loadOrders };

function init(){
  DOM.ordersList=document.getElementById('ordersList'); DOM.ordersEmpty=document.getElementById('ordersEmpty');
  DOM.orderDetailModal=document.getElementById('orderDetailModal');
  DOM.odModalMeal=document.getElementById('odModalMeal'); DOM.odModalPrice=document.getElementById('odModalPrice');
  DOM.odModalId=document.getElementById('odModalId'); DOM.odModalTimeline=document.getElementById('odModalTimeline');
  document.getElementById('modalClose').addEventListener('click',hideModal);
  document.querySelector('#orderDetailModal .modal-overlay').addEventListener('click',hideModal);
  // Bottom nav
  document.querySelectorAll('#page-orders .nav-item').forEach(function(item){
    item.addEventListener('click',function(){
      var p=item.getAttribute('data-page');
      if(p==='home') PageManager.navigate('home');
      else if(p==='orders') PageManager.navigate('orders');
      else if(p==='profile') PageManager.navigate('profile');
    });
  });
}
init();
})();

// ================================================================
// PAGE 07: 我的
// ================================================================
(function(){
var DOM={};

function toggleSection(header,body){
  var section=header.parentElement;
  if(section.classList.contains('profile-section--open')){section.classList.remove('profile-section--open');body.style.display='none';}
  else{section.classList.add('profile-section--open');body.style.display='block';}
}
async function loadRules(){
  var r=await API.getFamilyRules(); var rules=null;
  if(!r.error&&r.data) rules=r.data.rules||r.data;
  var saved=sessionStorage.getItem('familyRules');
  if(!rules&&saved){try{rules=JSON.parse(saved);}catch(e){}}
  if(!rules) rules={max_price:35,allowed_dietary:[],blocked_items:[],notify_on_unconfirm:true,unconfirm_timeout_minutes:30,notes:''};
  document.getElementById('prBudget').textContent='¥'+(rules.max_price||35)+' / 餐';
  var tags={
    low_oil:'低油',low_salt:'低盐',low_sugar:'低糖',soft_food:'软烂易消化',
    vegetarian:'素食',high_protein:'高蛋白',low_carb:'低碳水',gluten_free:'无麸质',
    halal:'清真',no_pork:'无猪肉',no_seafood:'无海鲜',low_purine:'低嘌呤'
  };
  var dLabels=(rules.allowed_dietary||[]).map(function(t){return tags[t]||t;});
  document.getElementById('prDietary').textContent=dLabels.length?dLabels.join('、'):'未设定';
  var blocked=rules.blocked_items||[];
  document.getElementById('prBlocked').textContent=blocked.length?blocked.join('、'):'无';
  document.getElementById('prNotify').textContent=rules.notify_on_unconfirm!==false?'已开启（'+(rules.unconfirm_timeout_minutes||30)+'分钟）':'已关闭';
  document.getElementById('prNotes').textContent=rules.notes||'无';
}
async function loadHistory(){
  // 历史订单（仅显示已完成的订单：已送达/已收餐/超时未确认/已取消）
  var COMPLETED=['delivered','confirmed','unconfirmed_timeout','cancelled'];
  var STATUS_MAP={delivered:'已送达',confirmed:'已收餐',unconfirmed_timeout:'超时未确认',cancelled:'已取消'};
  var r=await API.getFamilyOrders(); var orders=[];
  if(!r.error&&Array.isArray(r.data)) orders=r.data.filter(function(o){return COMPLETED.indexOf(o.status)>=0;});
  var oList=document.getElementById('historyOrdersList'), oEmpty=document.getElementById('historyOrdersEmpty');
  oList.innerHTML='';
  if(!orders.length){ oEmpty.style.display='block'; }
  else{ oEmpty.style.display='none';
    orders.slice(0,5).forEach(function(o){
      var item=document.createElement('div'); item.className='profile-mini-item';
      item.innerHTML='<div class="profile-mini-main"><span class="profile-mini-title">'+(o.meal_name||'餐品')+'</span><span class="profile-mini-sub">¥'+((o.meal_price||0).toFixed(2))+'</span></div><span class="profile-mini-right">'+(STATUS_MAP[o.status]||o.status)+'</span>';
      item.addEventListener('click',function(){ PageManager.navigate('orders'); });
      oList.appendChild(item);
    });
  }
  // 历史留言
  var mr=await API.getMessages(); var msgs=[];
  if(!mr.error&&Array.isArray(mr.data)) msgs=mr.data;
  var mList=document.getElementById('historyMsgsList'), mEmpty=document.getElementById('historyMsgsEmpty');
  mList.innerHTML='';
  if(!msgs.length){ mEmpty.style.display='block'; }
  else{ mEmpty.style.display='none';
    msgs.slice(-5).forEach(function(m){
      var item=document.createElement('div'); item.className='profile-mini-item';
      item.innerHTML='<div class="profile-mini-main"><span class="profile-mini-title">'+(m.content||'留言')+'</span><span class="profile-mini-sub">来自'+msgSenderName(m)+'</span></div><span class="profile-mini-right">'+(m.read?'已读':'未读')+'</span>';
      item.addEventListener('click',function(){ if(PageManager.pages['messages']) PageManager.navigate('messages'); });
      mList.appendChild(item);
    });
  }
}

function loadElderProfile(){
  var saved=localStorage.getItem('elderProfile');
  var name='张奶奶', info='78岁 · 女 · 138****8888';
  if(saved){
    try{
      var p=JSON.parse(saved);
      if(p&&p.name) name=p.name;
      var parts=[];
      if(p.age) parts.push(p.age+'岁');
      if(p.gender) parts.push(p.gender);
      if(p.phone) parts.push(maskPhone(p.phone));
      info=parts.length?parts.join(' · '):'未完善个人信息';
    }catch(e){}
  }
  var nEl=document.getElementById('profileElderName'); if(nEl) nEl.textContent=name;
  var iEl=document.getElementById('profileElderInfo'); if(iEl) iEl.textContent=info;
}
function maskPhone(phone){
  var s=String(phone||'');
  return s.length>=7?s.slice(0,3)+'****'+s.slice(-4):s;
}

PageManager.pageHooks.profile = { onEnter:function(){loadElderProfile();loadRules();loadHistory();} };

function init(){
  document.getElementById('rulesHeader').addEventListener('click',function(){toggleSection(this,document.getElementById('rulesBody'));});
  document.getElementById('historyOrdersHeader').addEventListener('click',function(){toggleSection(this,document.getElementById('historyOrdersBody'));});
  document.getElementById('historyMsgsHeader').addEventListener('click',function(){toggleSection(this,document.getElementById('historyMsgsBody'));});
  // 个人信息栏 → 进入个人信息编辑页
  var elderCard=document.getElementById('profileElderCard');
  if(elderCard) elderCard.addEventListener('click',function(){ PageManager.navigate('profile-edit'); });
  // Bottom nav
  document.querySelectorAll('#page-profile .nav-item').forEach(function(item){
    item.addEventListener('click',function(){
      var p=item.getAttribute('data-page');
      if(p==='home') PageManager.navigate('home');
      else if(p==='orders') PageManager.navigate('orders');
      else if(p==='profile') PageManager.navigate('profile');
    });
  });
}
init();
})();

// ================================================================
// PAGE 08: 个人信息编辑
// ================================================================
(function(){
var DOM={};

function loadForm(){
  var saved=localStorage.getItem('elderProfile');
  var p=saved?JSON.parse(saved):{name:'张奶奶',age:78,gender:'女',phone:'13800008888',junior:'女儿'};
  DOM.name.value=p.name||'';
  DOM.age.value=p.age||'';
  DOM.gender.value=p.gender||'女';
  DOM.phone.value=p.phone||'';
  DOM.junior.value=p.junior||'';
}
function saveProfile(){
  var name=DOM.name.value.trim();
  var age=DOM.age.value.trim();
  var gender=DOM.gender.value;
  var phone=DOM.phone.value.trim();
  var junior=DOM.junior.value.trim();
  if(!name){ showToast('请输入姓名','error'); DOM.name.focus(); return; }
  if(age && (Number(age)<50||Number(age)>120)){ showToast('请输入合理的年龄（50-120）','error'); DOM.age.focus(); return; }
  if(phone && !/^1\d{10}$/.test(phone)){ showToast('请输入正确的11位手机号','error'); DOM.phone.focus(); return; }
  var profile={name:name, age:age?Number(age):'', gender:gender, phone:phone||'', junior:junior||''};
  localStorage.setItem('elderProfile',JSON.stringify(profile));
  showToast('个人信息已保存','success');
  PageManager.navigate('profile');
}
function goBack(){ PageManager.navigate('profile'); }

PageManager.pageHooks['profile-edit'] = {
  onEnter: function(){ loadForm(); },
  onLeave: function(){}
};

function init(){
  DOM.name=document.getElementById('editName');
  DOM.age=document.getElementById('editAge');
  DOM.gender=document.getElementById('editGender');
  DOM.phone=document.getElementById('editPhone');
  DOM.junior=document.getElementById('editJunior');
  document.getElementById('profileEditBack').addEventListener('click',goBack);
  document.getElementById('editSaveBtn').addEventListener('click',saveProfile);
}
init();
})();

// ================================================================
// 家属留言实时通知
// ================================================================
(function(){
var popup=document.getElementById('msgPopup'), lastMsgId=null, hideTimer=null;

function fmtTime(iso){ try{var d=new Date(iso);return String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0');}catch(e){return'';} }
function playChime(){
  try{
    var ctx=new(window.AudioContext||window.webkitAudioContext)();
    var o=ctx.createOscillator(),g=ctx.createGain();
    o.connect(g);g.connect(ctx.destination);
    o.type='sine';o.frequency.setValueAtTime(880,ctx.currentTime);o.frequency.setValueAtTime(1100,ctx.currentTime+.12);
    g.gain.setValueAtTime(.3,ctx.currentTime);g.gain.exponentialRampToValueAtTime(.01,ctx.currentTime+.45);
    o.start(ctx.currentTime);o.stop(ctx.currentTime+.45);
  }catch(e){}
}
function showPopup(msg){
  document.getElementById('msgPopupFrom').textContent=msgSenderName(msg)+'给您留言';
  document.getElementById('msgPopupBody').textContent=msg.content||'';
  document.getElementById('msgPopupTime').textContent=fmtTime(msg.created_at);
  popup.classList.remove('hide');
  popup.style.animation='none'; popup.offsetHeight; popup.style.animation='msgSlideDown .4s cubic-bezier(0.16,1,0.3,1)';
  playChime();
  clearTimeout(hideTimer);
  hideTimer=setTimeout(hidePopup,10000);
}
function hidePopup(){ popup.classList.add('hide'); }

// 点击弹窗进入留言页面；关闭按钮仅隐藏
if(popup){
  popup.addEventListener('click',function(){ hidePopup(); if(PageManager.pages['messages']) PageManager.navigate('messages'); });
  var close=document.getElementById('msgPopupClose'); if(close) close.addEventListener('click',function(e){e.stopPropagation();hidePopup();});
}

// 轮询未读留言
setInterval(async function(){
  try{
    var r=await API.getUnreadMessages();
    if(!r.error&&Array.isArray(r.data)&&r.data.length>0){
      var unread=r.data.slice().sort(function(a,b){return new Date(b.created_at)-new Date(a.created_at);});
      if(unread[0].id!==lastMsgId){
        lastMsgId=unread[0].id;
        showPopup(unread[0]);
        API.markMessageRead(unread[0].id);
      }
    }
  }catch(e){}
},4000);
})();

// ================================================================
// 家属留言页面
// ================================================================
(function(){
var DOM={};
function fmtMsgTime(iso){
  if(!iso) return '';
  try{var d=new Date(iso);return (d.getMonth()+1)+'月'+d.getDate()+'日 '+String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0');}catch(e){return '';}
}
function escapeHtml(s){var d=document.createElement('div');d.textContent=s;return d.innerHTML;}
function renderMessage(m){
  DOM.thread.appendChild((function(){
    var item=document.createElement('div'); item.className='msg-chat-item';
    item.innerHTML='<span class="msg-chat-from">'+escapeHtml(msgSenderName(m))+'</span>'
      +'<div class="msg-chat-bubble">'+escapeHtml(m.content||'')+'</div>'
      +'<span class="msg-chat-time">'+fmtMsgTime(m.created_at)+'</span>';
    return item;
  })());
  DOM.thread.scrollTop=DOM.thread.scrollHeight;
}
async function loadMessages(){
  DOM.thread.innerHTML='';
  DOM.empty.style.display='flex';
  var r=await API.getMessages();
  if(!r.error&&Array.isArray(r.data)&&r.data.length>0){
    DOM.empty.style.display='none';
    r.data.slice().sort(function(a,b){return new Date(a.created_at)-new Date(b.created_at);}).forEach(function(m){ renderMessage(m); });
  }
}
PageManager.pageHooks.messages = { onEnter:loadMessages };
function init(){
  DOM.thread=document.getElementById('elderMsgThread');
  DOM.empty=document.getElementById('elderMsgEmpty');
  document.getElementById('elderMessagesBack').addEventListener('click',function(){PageManager.back('profile');});
}
init();
})();

// ===== 全局启动 =====
PageManager.init();
console.log('🍚 饭心 AI · 银龄放心单 SPA 初始化完成');
})();
