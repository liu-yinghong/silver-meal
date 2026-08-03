/* ============================================================
   饭心 · 家属端 — 统一交互逻辑
   包含 B-01 ~ B-04 全部页面逻辑 + PageManager 路由
   ============================================================ */
(function(){
'use strict';

// ===== PageManager =====
var PageManager = {
  current:'status', pages:{}, pageHooks:{}, _history:[],
  init:function(){
    var self=this;
    document.querySelectorAll('.page').forEach(function(p){self.pages[p.id.replace('page-','')]=p;});
    document.querySelectorAll('[data-back]').forEach(function(btn){
      btn.addEventListener('click',function(){self.back(this.getAttribute('data-back'));});
    });
  },
  navigate:function(name, opts){
    opts=opts||{};
    if(this.current===name) return;
    var old=this.pages[this.current], nue=this.pages[name];
    if(!nue){console.warn('PageManager: unknown page "'+name+'"');return;}
    if(!opts.noHistory) this._history.push(this.current);
    if(old){old.classList.remove('page--active');}
    if(nue){nue.classList.add('page--active');}
    if(this.pageHooks[this.current]&&this.pageHooks[this.current].onLeave) this.pageHooks[this.current].onLeave();
    this.current=name;
    if(this.pageHooks[name]&&this.pageHooks[name].onEnter) this.pageHooks[name].onEnter();
    window.scrollTo({top:0,behavior:'smooth'});
  },
  // 返回上一页；无历史时回退到 fallback
  back:function(fallback){
    var target=null;
    while(this._history.length){
      var t=this._history.pop();
      if(t!==this.current&&this.pages[t]){ target=t; break; }
    }
    if(!target) target=fallback||'status';
    this.navigate(target,{noHistory:true});
  }
};

// ===== 全局 Toast =====
var toastEl=document.getElementById('toast'),toastTimer=null;
function showToast(msg,type){
  if(!type)type='info';if(toastTimer)clearTimeout(toastTimer);
  toastEl.textContent=msg;toastEl.className='toast toast--visible';
  if(type==='error')toastEl.classList.add('toast--error');
  if(type==='success')toastEl.classList.add('toast--success');
  toastTimer=setTimeout(function(){toastEl.classList.remove('toast--visible');},2500);
}

// ==============================
// 全局数据
// ==============================
var currentOrder=null;      // 当前订单数据
var orderStatus='';         // 订单状态
var messages=[];            // 留言列表

// ==============================
// PAGE B-01: 今日状态
// ==============================
(function(){
var DOM={}, pollingTimer=null;

function fmtTime(iso){
  if(!iso) return '';
  try{var d=new Date(iso);return String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0');}catch(e){return '';}
}
function setElderName(){
  // 长辈称呼：根据个人信息绑定的关注长辈（姓 + 性别）
  var name='张奶奶';
  var saved=localStorage.getItem('familyProfile');
  if(saved){
    try{
      var p=JSON.parse(saved);
      var elder=p&&p.elder?String(p.elder).trim():'';
      var g=p&&p.elderGender?p.elderGender:'';
      if(elder){
        if(/奶奶|爷爷|阿姨|叔叔|伯伯|女士|先生/.test(elder)){ name=elder; }
        else{
          var title=g==='男'?'爷爷':(g==='保密'?'长辈':'奶奶');
          name=elder.charAt(0)+title;
        }
      }
    }catch(e){}
  }
  var nEl=document.getElementById('homeElderName'); if(nEl) nEl.textContent=name;
}
function updateElderStatus(status, order){
  var dot=DOM.elderStatusDot, text=DOM.elderStatusText;
  dot.classList.remove('status--warning','status--idle');
  if(!status||status==='none'){
    text.textContent='今日暂无订单'; dot.classList.add('status--idle');
  }else if(status==='delivered'){
    text.textContent='餐品已送达，等待确认收餐'; dot.classList.add('status--warning');
  }else if(status==='confirmed'){
    // 显示最近一次完成的订单名称 + 完成时间，如：番茄鸡蛋面 12:00
    var meal=order&&order.meal_name?order.meal_name:'已收餐';
    var t=fmtTime(order&&(order.confirmed_at||order.updated_at));
    text.textContent=t?meal+' '+t:meal+' ✓';
  }else if(status==='cancelled'){
    text.textContent='今日订单已取消'; dot.classList.add('status--idle');
  }else if(status==='unconfirmed_timeout'){
    text.textContent='餐品超时未确认'; dot.classList.add('status--warning');
  }else{
    var map={created:'今日已下单',paid:'已支付，等待商家接单',preparing:'商家正在制作中',delivering:'餐品配送中'};
    text.textContent=map[status]||'今日已下单，餐品配送中';
  }
}
function updateOrderCard(order){
  currentOrder=order; orderStatus=order?order.status:null;
  var body=DOM.orderCardBody, empty=DOM.orderCardEmpty, badge=DOM.orderStatusBadge;
  if(!order){
    body.style.display='none'; empty.style.display='flex'; badge.style.display='none';
    updateElderStatus('none', null); return;
  }
  body.style.display='block'; empty.style.display='none'; badge.style.display='inline-block';
  DOM.orderMealName.textContent=order.meal_name||'--';
  DOM.orderMealPrice.textContent='¥'+((order.meal_price||0).toFixed(2));
  DOM.orderEta.textContent='预计 '+(order.eta_minutes||'--')+' 分钟';
  DOM.orderRulePass.textContent=order.rule_passed!==false?'规则已通过':'需关注';
  // 餐品图片：按 meal_id 构造 /elder/images/{meal_id}_ui.png
  var mid=order.meal_id||'', svg=DOM.orderMealIcon?DOM.orderMealIcon.querySelector('svg'):null;
  if(mid){
    DOM.orderMealImage.onerror=function(){ DOM.orderMealImage.style.display='none'; if(svg) svg.style.display='block'; };
    DOM.orderMealImage.src='/elder/images/'+mid+'_ui.png?v=20260802';
    DOM.orderMealImage.style.display='block';
    if(svg) svg.style.display='none';
  }else{
    DOM.orderMealImage.style.display='none';
    if(svg) svg.style.display='block';
  }
  var statusMap={created:'已下单',paid:'已支付',preparing:'制作中',delivering:'配送中',delivered:'已送达',confirmed:'已收餐',cancelled:'已取消',unconfirmed_timeout:'超时未确认'};
  badge.textContent=statusMap[order.status]||order.status||'--';
  badge.classList.remove('status--done');
  if(order.status==='delivered'||order.status==='confirmed') badge.classList.add('status--done');
  updateElderStatus(order.status, order);
}
var initialOrderLoaded=false;
async function loadOrderData(isPoll){
  var r=await API.getFamilyOrders();
  if(!r.error&&Array.isArray(r.data)&&r.data.length>0){
    updateOrderCard(r.data[0]); initialOrderLoaded=true;
  }else{
    // 无真实订单 → 显示空状态（与老人端一致）
    updateOrderCard(null);
  }
}

PageManager.pageHooks.status = {
  onEnter:function(){ setElderName(); loadOrderData(); startPolling(); },
  onLeave:function(){ if(pollingTimer)clearInterval(pollingTimer); }
};
function startPolling(){
  if(pollingTimer)clearInterval(pollingTimer);
  pollingTimer=setInterval(function(){loadOrderData(true);},8000);
}

function init(){
  DOM.elderStatusText=document.getElementById('elderStatusText');
  DOM.elderStatusDot=document.getElementById('elderStatusDot');
  DOM.orderCardBody=document.getElementById('orderCardBody');
  DOM.orderCardEmpty=document.getElementById('orderCardEmpty');
  DOM.orderStatusBadge=document.getElementById('orderStatusBadge');
  DOM.orderMealName=document.getElementById('orderMealName');
  DOM.orderMealPrice=document.getElementById('orderMealPrice');
  DOM.orderMealImage=document.getElementById('orderMealImage');
  DOM.orderMealIcon=document.querySelector('#todayOrderCard .order-meal-icon');
  DOM.orderEta=document.getElementById('orderEta');
  DOM.orderRulePass=document.getElementById('orderRulePass');
  document.getElementById('viewOrderBtn').addEventListener('click',function(){
    if(!currentOrder){showToast('暂无订单');return;}
    PageManager.navigate('orderdetail');
  });
  document.getElementById('leaveMsgBtn').addEventListener('click',function(){PageManager.navigate('messages');});
  document.getElementById('viewAnalysisBtn').addEventListener('click',function(){PageManager.navigate('analysis');});
  document.getElementById('settingsBtn').addEventListener('click',function(){PageManager.navigate('settings');});
  // Bottom nav
  document.querySelectorAll('#page-status .nav-item').forEach(function(item){
    item.addEventListener('click',function(){
      var p=item.getAttribute('data-page');
      document.querySelectorAll('#page-status .nav-item').forEach(function(n){n.classList.remove('nav-item--active');});
      item.classList.add('nav-item--active');
      if(p==='orders') PageManager.navigate('family-orders');
      else if(p==='profile') PageManager.navigate('profile');
    });
  });
  loadOrderData(); startPolling();
  setElderName();
}
init();
})();

// ==============================
// PAGE B-02: AI 分析
// ==============================
(function(){
var DOM={};
function iconFor(status){
  if(status==='match') return '<svg viewBox="0 0 24 24" width="20" height="20"><circle cx="12" cy="12" r="10" fill="#35B84A" opacity=".15"/><path d="M7 12L10.5 15.5L17 9" stroke="#35B84A" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  if(status==='warn') return '<svg viewBox="0 0 24 24" width="20" height="20"><circle cx="12" cy="12" r="10" fill="#C63B2F" opacity=".15"/><path d="M12 8V13" stroke="#C63B2F" stroke-width="2.5" stroke-linecap="round"/><circle cx="12" cy="16.5" r="1" fill="#C63B2F"/></svg>';
  return '<svg viewBox="0 0 24 24" width="20" height="20"><circle cx="12" cy="12" r="10" stroke="#F28C28" stroke-width="2"/><line x1="12" y1="7" x2="12" y2="12" stroke="#F28C28" stroke-width="2" stroke-linecap="round"/><circle cx="12" cy="16" r="1" fill="#F28C28"/></svg>';
}
function renderMatches(matches){
  DOM.ruleMatchList.innerHTML='';
  (matches||[]).forEach(function(m){
    var item=document.createElement('div');
    item.className='rule-item rule-item--'+(m.status||'info');
    item.innerHTML='<div class="rule-icon">'+iconFor(m.status)+'</div><div class="rule-content"><span class="rule-label">'+(m.label||'')+'</span><span class="rule-desc">'+(m.desc||'')+'</span></div>';
    DOM.ruleMatchList.appendChild(item);
  });
}
function renderSuitability(pct){
  pct=Math.max(0,Math.min(100,Math.round(pct||0)));
  DOM.analysisScore.textContent=pct+'%';
  var ring=DOM.analysisScore.parentElement.querySelector('circle:nth-child(2)');
  if(ring) ring.setAttribute('stroke-dashoffset',String(176*(1-pct/100)));
}
async function loadAnalysis(){
  DOM.summaryText.textContent='AI 正在分析家属设定的饮食规则与推荐餐食的匹配，请稍候...';
  DOM.analysisScore.textContent='--%';
  DOM.suitabilityDesc.textContent='大模型评估中...';
  DOM.ruleMatchList.innerHTML='<div class="rule-loading">🤖 大模型正在分析规则匹配...</div>';
  var r=await API.getAnalysis();
  if(r.error){ DOM.summaryText.textContent='分析暂不可用，请稍后重试'; DOM.ruleMatchList.innerHTML=''; DOM.suitabilityDesc.textContent='暂无法获取分析结果'; return; }
  var d=r.data||{};
  DOM.summaryText.textContent=d.summary||'暂无分析';
  renderMatches(d.matches);
  renderSuitability(d.suitability);
  var s=d.suitability||0;
  DOM.suitabilityDesc.textContent=s>=80?'餐品与家属规则匹配度高，推荐可信':s>=60?'餐品基本符合家属规则':s>=40?'餐品与家属规则部分匹配':'餐品与家属规则匹配度较低，建议关注';
}
PageManager.pageHooks.analysis = { onEnter:loadAnalysis };
function init(){
  DOM.summaryText=document.getElementById('analysisSummaryText');
  DOM.ruleMatchList=document.getElementById('ruleMatchList');
  DOM.analysisScore=document.getElementById('analysisScore');
  DOM.suitabilityDesc=document.getElementById('suitabilityDesc');
}
init();
})();

// ==============================
// PAGE B-03: 订单详情
// ==============================
(function(){
var DOM={};
function renderOrderDetail(){
  if(!currentOrder){ showToast('暂无订单数据'); return; }
  DOM.odMealName.textContent=currentOrder.meal_name||'--';
  DOM.odMealPrice.textContent='¥'+((currentOrder.meal_price||0).toFixed(2));
  DOM.odOrderId.textContent=currentOrder.order_id||'--';
  var sm={created:'已下单',paid:'已支付',preparing:'制作中',delivering:'配送中',delivered:'已送达',confirmed:'已收餐',cancelled:'已取消',unconfirmed_timeout:'超时未确认'};
  DOM.odStatusTag.textContent=sm[currentOrder.status]||currentOrder.status||'--';
  // Timeline
  var steps=document.querySelectorAll('#page-orderdetail .ot-step'), statusOrder=['created','paid','preparing','delivering','delivered'];
  var currentIdx=statusOrder.indexOf(currentOrder.status); if(currentIdx<0)currentIdx=0;
  steps.forEach(function(s,i){
    s.classList.remove('ot-step--done','ot-step--active');
    if(i<currentIdx) s.classList.add('ot-step--done');
    else if(i===currentIdx) s.classList.add('ot-step--active');
  });
  // Times from order data
  var times={created:currentOrder.created_at,paid:currentOrder.updated_at,preparing:currentOrder.updated_at,delivering:currentOrder.updated_at};
  ['created','paid','preparing','delivering'].forEach(function(st,i){
    var el=document.getElementById('otTime'+st.charAt(0).toUpperCase()+st.slice(1));
    if(!el) return;
    if(i<=currentIdx&&times[st]) el.textContent=formatTime(times[st]);
    else if(i===currentIdx+1) el.textContent=currentOrder.status==='delivered'?'已到达':'预计 '+estimateTime(currentOrder.eta_minutes||35);
    else el.textContent='--';
  });
  // Receipt alert
  DOM.receiptAlert.style.display=currentOrder.status==='delivered'&&!currentOrder.confirmed?'flex':'none';
}
function formatTime(iso){
  if(!iso)return'--'; try{var d=new Date(iso);return d.getHours().toString().padStart(2,'0')+':'+d.getMinutes().toString().padStart(2,'0');}catch(e){return'--';}
}
function estimateTime(mins){
  var d=new Date(Date.now()+mins*60000); return d.getHours().toString().padStart(2,'0')+':'+d.getMinutes().toString().padStart(2,'0');
}
var callTimerInterval=null;
function handleContact(){
  var modal=document.getElementById('callModal');
  var status=document.getElementById('callStatus');
  var timer=document.getElementById('callTimer');
  modal.style.display='flex'; status.textContent='正在呼叫...'; timer.style.display='none';
  hangupCall(true);
  callTimerTimeout=setTimeout(function(){
    status.textContent='通话中';
    timer.style.display='block'; timer.textContent='00:00';
    var sec=0;
    callTimerInterval=setInterval(function(){sec++;var m=Math.floor(sec/60),s=sec%60;timer.textContent=(m<10?'0'+m:m)+':'+(s<10?'0'+s:s);},1000);
  },2000);
  // 真实订单才调用后端，模拟订单（DEMO/OFFLINE）不产生无效请求
  var oid=currentOrder?currentOrder.order_id:'';
  if(oid&&oid.indexOf('DEMO')===-1&&oid.indexOf('OFFLINE')===-1){
    API.contactElder(oid,'call');
  }
}
var callTimerTimeout=null;
function hangupCall(resetOnly){
  if(callTimerInterval){clearInterval(callTimerInterval);callTimerInterval=null;}
  if(callTimerTimeout){clearTimeout(callTimerTimeout);callTimerTimeout=null;}
  if(!resetOnly){
    var modal=document.getElementById('callModal'); if(modal) modal.style.display='none';
    showToast('📞 通话结束（模拟）');
  }
}

var orderdetailNavBound=false;
PageManager.pageHooks.orderdetail = {
  onEnter:function(){renderOrderDetail(); if(!orderdetailNavBound){bindOrderdetailNav();orderdetailNavBound=true;}},
  onLeave:function(){hangupCall(false);}
};

function bindOrderdetailNav(){
  document.querySelectorAll('#page-orderdetail .nav-item').forEach(function(item){
    item.addEventListener('click',function(){
      var p=item.getAttribute('data-page');
      if(p==='status') PageManager.navigate('status');
      else if(p==='orders') PageManager.navigate('family-orders');
      else if(p==='profile') PageManager.navigate('profile');
    });
  });
}

function init(){
  DOM.odMealName=document.getElementById('odMealName'); DOM.odMealPrice=document.getElementById('odMealPrice');
  DOM.odOrderId=document.getElementById('odOrderId'); DOM.odStatusTag=document.getElementById('odStatusTag');
  DOM.receiptAlert=document.getElementById('receiptAlert');
  var ceb=document.getElementById('contactElderBtn'); if(ceb) ceb.addEventListener('click',handleContact);
  var chb=document.getElementById('callHangupBtn'); if(chb) chb.addEventListener('click',function(){hangupCall();});
}
init();
})();

// ==============================
// PAGE B-04: 家属留言
// ==============================
(function(){
var DOM={};

function renderMessage(msg){
  var thread=DOM.messageThread;
  // Hide empty state
  var empty=document.getElementById('msgEmpty'); if(empty)empty.style.display='none';
  var div=document.createElement('div'); div.className='msg-bubble msg-bubble--me';
  div.innerHTML='<div class="msg-bubble-content">'+escapeHtml(msg.content||msg)+'</div><div class="msg-bubble-time">'+formatMsgTime(msg.created_at||new Date().toISOString())+'</div>';
  thread.appendChild(div);
  thread.scrollTop=thread.scrollHeight;
}
function escapeHtml(s){var d=document.createElement('div');d.textContent=s;return d.innerHTML;}
function formatMsgTime(iso){try{var d=new Date(iso),h=d.getHours().toString().padStart(2,'0'),m=d.getMinutes().toString().padStart(2,'0');return h+':'+m;}catch(e){return'';}}
function getFamilyMemberName(){
  var saved=localStorage.getItem('familyProfile');
  if(saved){
    try{var p=JSON.parse(saved); if(p&&p.name&&String(p.name).trim()) return String(p.name).trim();}catch(e){}
  }
  return '女儿';
}

async function loadMessages(){
  messages=[]; DOM.messageThread.innerHTML='';
  var empty=document.getElementById('msgEmpty'); if(empty)empty.style.display='flex';
  var r=await API.getMessages();
  if(!r.error&&Array.isArray(r.data)&&r.data.length>0){
    if(empty)empty.style.display='none';
    r.data.slice().sort(function(a,b){return new Date(a.created_at)-new Date(b.created_at);}).forEach(function(m){messages.push(m);renderMessage(m);});
  }
}
async function handleSend(){
  var input=DOM.msgInput, text=input.value.trim(); if(!text){showToast('请输入留言内容');return;}
  DOM.msgSendBtn.disabled=true;
  var mr=await API.sendMessage(text, getFamilyMemberName());
  if(mr.error){
    renderMessage({content:text,created_at:new Date().toISOString()});
    showToast('离线模式 · 留言已显示（未发送到后端）');
  }else{
    showToast('留言已发送','success');
    renderMessage({content:text,created_at:mr.data.created_at||new Date().toISOString()});
  }
  input.value=''; DOM.msgSendBtn.disabled=true;
}

PageManager.pageHooks.messages = { onEnter:loadMessages };

function init(){
  DOM.messageThread=document.getElementById('messageThread');
  DOM.msgInput=document.getElementById('msgInput'); DOM.msgSendBtn=document.getElementById('msgSendBtn');
  DOM.msgInput.addEventListener('input',function(){DOM.msgSendBtn.disabled=!DOM.msgInput.value.trim();});
  DOM.msgInput.addEventListener('keypress',function(e){if(e.key==='Enter'){e.preventDefault();handleSend();}});
  DOM.msgSendBtn.addEventListener('click',handleSend);
}
init();
})();

// ==============================
// PAGE B-05: 饮食规则
// ==============================
(function(){
var DOM={}, defaultRules={max_price:35,allowed_dietary:['low_oil','low_salt'],blocked_items:[],notify_on_unconfirm:true,unconfirm_timeout_minutes:30,notes:''};

function getCurrentRules(){
  return {
    max_price:parseInt(DOM.budgetInput.value)||35,
    allowed_dietary:getCheckedDietary(),
    blocked_items:getBlockedItems(),
    notify_on_unconfirm:DOM.notifyToggle.checked,
    unconfirm_timeout_minutes:parseInt(DOM.timeoutSelect.value)||30,
    notes:DOM.notesInput.value.trim(),
  };
}
function getCheckedDietary(){
  var result=[];
  document.querySelectorAll('#dietaryOptions input[type=checkbox]:checked').forEach(function(cb){result.push(cb.value);});
  return result;
}
function getBlockedItems(){
  var items=[];
  document.querySelectorAll('#blockedTags .blocked-tag').forEach(function(tag){
    var text=tag.textContent.replace('×','').trim(); if(text) items.push(text);
  });
  return items;
}
function setBlockedTags(items){
  DOM.blockedTags.innerHTML='';
  items.forEach(function(item){
    var tag=document.createElement('span'); tag.className='blocked-tag';
    tag.innerHTML=item+' <button class="blocked-tag-remove" data-item="'+item+'">×</button>';
    DOM.blockedTags.appendChild(tag);
  });
  bindTagRemoval();
}
function bindTagRemoval(){
  document.querySelectorAll('#blockedTags .blocked-tag-remove').forEach(function(btn){
    btn.addEventListener('click',function(){
      this.parentElement.remove();
    });
  });
}
function setDefaultBlockedTags(){ setBlockedTags(defaultRules.blocked_items); }
function addBlockedItem(item){
  item=item.trim(); if(!item) return;
  var items=getBlockedItems();
  if(items.includes(item)){showToast('该食材已存在');return;}
  items.push(item); setBlockedTags(items);
}
async function loadRules(){
  var r=await API.getFamilyRules();
  if(!r.error&&r.data){
    var rules=r.data.rules||r.data;
    DOM.budgetInput.value=rules.max_price||35; DOM.budgetSlider.value=rules.max_price||35;
    document.querySelectorAll('#dietaryOptions input[type=checkbox]').forEach(function(cb){
      cb.checked=(rules.allowed_dietary||['low_oil','low_salt']).includes(cb.value);
    });
    setBlockedTags(rules.blocked_items||[]);
    DOM.notifyToggle.checked=rules.notify_on_unconfirm!==false; DOM.timeoutSelect.value=rules.unconfirm_timeout_minutes||30;
    DOM.notesInput.value=rules.notes||''; updateNotesCount();
    updateTimeoutVisibility();
  }else{
    // 离线：先尝试读取本地暂存的规则
    var saved=sessionStorage.getItem('familyRules');
    var rules=saved?JSON.parse(saved):defaultRules;
    DOM.budgetInput.value=rules.max_price||35; DOM.budgetSlider.value=rules.max_price||35;
    setBlockedTags(rules.blocked_items||[]);
    DOM.notifyToggle.checked=rules.notify_on_unconfirm!==false; DOM.timeoutSelect.value=rules.unconfirm_timeout_minutes||30;
    DOM.notesInput.value=rules.notes||''; updateNotesCount();
    updateTimeoutVisibility();
  }
}
function updateNotesCount(){
  var len=DOM.notesInput.value.length;
  DOM.notesCount.textContent=len+' / 200';
}
function updateTimeoutVisibility(){
  DOM.timeoutRow.style.display=DOM.notifyToggle.checked?'flex':'none';
}
function buildRulesPreview(rules){
  var prefMap={low_oil:'低油',low_salt:'低盐',low_sugar:'低糖',soft_food:'软烂易消化',vegetarian:'素食',high_protein:'高蛋白',low_carb:'低碳水',gluten_free:'无麸质',halal:'清真',no_pork:'无猪肉',no_seafood:'无海鲜',low_purine:'低嘌呤'};
  var prefs=(rules.allowed_dietary||[]).map(function(t){return prefMap[t]||t;});
  var blocked=rules.blocked_items||[];
  var rows='';
  rows+='<div class="rp-row"><span class="rp-label">单餐预算</span><span class="rp-value">¥'+(rules.max_price||35)+' / 餐</span></div>';
  rows+='<div class="rp-row"><span class="rp-label">饮食偏好</span><span class="rp-value">'+(prefs.length?prefs.join('、'):'未设定')+'</span></div>';
  rows+='<div class="rp-row"><span class="rp-label">禁忌食材</span><span class="rp-value">'+(blocked.length?blocked.join('、'):'无')+'</span></div>';
  rows+='<div class="rp-row"><span class="rp-label">超时提醒</span><span class="rp-value">'+(rules.notify_on_unconfirm!==false?'开启（'+(rules.unconfirm_timeout_minutes||30)+'分钟）':'关闭')+'</span></div>';
  rows+='<div class="rp-row"><span class="rp-label">备注</span><span class="rp-value">'+(rules.notes||'无')+'</span></div>';
  return rows;
}
function handleSave(){
  var rules=getCurrentRules();
  document.getElementById('rulesConfirmPreview').innerHTML=buildRulesPreview(rules);
  document.getElementById('rulesConfirmOverlay').style.display='flex';
}
function hideRulesConfirm(){
  document.getElementById('rulesConfirmOverlay').style.display='none';
}
async function confirmRulesSave(){
  hideRulesConfirm();
  var rules=getCurrentRules();
  DOM.saveBtn.disabled=true; DOM.saveBtn.textContent='保存中...';
  var sr=await API.saveFamilySettings(rules);
  if(sr.error&&sr.error.code==='NETWORK_ERROR'){
    showToast('离线模式 · 规则已暂存在本地','success');
    sessionStorage.setItem('familyRules',JSON.stringify(rules));
  }else if(sr.error){
    showToast('保存失败，请重试','error');
  }else{
    showToast('饮食规则已保存','success');
    sessionStorage.setItem('familyRules',JSON.stringify(rules));
  }
  DOM.saveBtn.disabled=false; DOM.saveBtn.textContent='保存规则';
}
function handleReset(){
  DOM.budgetInput.value=defaultRules.max_price; DOM.budgetSlider.value=defaultRules.max_price;
  document.querySelectorAll('#dietaryOptions input[type=checkbox]').forEach(function(cb){
    cb.checked=defaultRules.allowed_dietary.includes(cb.value);
  });
  setBlockedTags(defaultRules.blocked_items);
  DOM.notifyToggle.checked=defaultRules.notify_on_unconfirm;
  DOM.timeoutSelect.value=defaultRules.unconfirm_timeout_minutes;
  DOM.notesInput.value=defaultRules.notes; updateNotesCount();
  updateTimeoutVisibility();
  showToast('已恢复默认设置');
}

PageManager.pageHooks.settings = { onEnter:loadRules };

function init(){
  DOM.budgetInput=document.getElementById('budgetInput'); DOM.budgetSlider=document.getElementById('budgetSlider');
  DOM.notifyToggle=document.getElementById('notifyToggle'); DOM.timeoutSelect=document.getElementById('timeoutSelect');
  DOM.timeoutRow=document.getElementById('timeoutRow'); DOM.notesInput=document.getElementById('notesInput');
  DOM.notesCount=document.getElementById('notesCount'); DOM.blockedTags=document.getElementById('blockedTags');
  DOM.saveBtn=document.getElementById('saveSettingsBtn');
  // Budget slider sync
  DOM.budgetSlider.addEventListener('input',function(){DOM.budgetInput.value=this.value;});
  DOM.budgetInput.addEventListener('input',function(){var v=parseInt(this.value)||35;if(v<10)v=10;if(v>200)v=200;this.value=v;DOM.budgetSlider.value=v;});
  // Notify toggle
  DOM.notifyToggle.addEventListener('change',updateTimeoutVisibility);
  // Notes count
  DOM.notesInput.addEventListener('input',updateNotesCount);
  // Blocked items
  document.getElementById('blockedAddBtn').addEventListener('click',function(){
    var input=document.getElementById('blockedInput'); addBlockedItem(input.value); input.value='';
  });
  document.getElementById('blockedInput').addEventListener('keypress',function(e){if(e.key==='Enter'){e.preventDefault();document.getElementById('blockedAddBtn').click();}});
  bindTagRemoval();
  // Save / Reset
  DOM.saveBtn.addEventListener('click',handleSave);
  document.getElementById('resetSettingsBtn').addEventListener('click',handleReset);
  // 规则确认弹窗
  document.getElementById('rulesConfirmBack').addEventListener('click',hideRulesConfirm);
  document.getElementById('rulesConfirmSave').addEventListener('click',confirmRulesSave);
  var rulesOv=document.getElementById('rulesConfirmOverlay');
  if(rulesOv) rulesOv.addEventListener('click',function(e){ if(e.target===this) hideRulesConfirm(); });
}
init();
})();

// ==============================
// PAGE B-06: 个人
// ==============================
(function(){
function loadFamilyProfile(){
  var saved=localStorage.getItem('familyProfile');
  var name='女儿', elder='张奶奶', info='关注长辈：张奶奶';
  if(saved){
    try{
      var p=JSON.parse(saved);
      if(p&&p.name) name=p.name;
      if(p&&p.elder) elder=p.elder;
      var parts=[];
      if(p.age) parts.push(p.age+'岁');
      if(p.gender) parts.push(p.gender);
      if(p.phone) parts.push(maskPhone(p.phone));
      info='关注长辈：'+elder+(parts.length?(' · '+parts.join(' · ')):'');
    }catch(e){}
  }
  var nEl=document.getElementById('familyProfileName'); if(nEl) nEl.textContent=name;
  var iEl=document.getElementById('familyProfileInfo'); if(iEl) iEl.textContent=info;
}
function maskPhone(phone){
  var s=String(phone||'');
  return s.length>=7?s.slice(0,3)+'****'+s.slice(-4):s;
}
function loadFamilyRules(){
  var prefMap={low_oil:'低油',low_salt:'低盐',low_sugar:'低糖',soft_food:'软烂易消化',vegetarian:'素食',high_protein:'高蛋白',low_carb:'低碳水',gluten_free:'无麸质',halal:'清真',no_pork:'无猪肉',no_seafood:'无海鲜',low_purine:'低嘌呤'};
  var empty={max_price:35,allowed_dietary:[],blocked_items:[],notify_on_unconfirm:true,unconfirm_timeout_minutes:30,notes:''};
  var rules=null;
  var saved=sessionStorage.getItem('familyRules');
  if(saved){ try{ rules=JSON.parse(saved); }catch(e){} }
  API.getFamilyRules().then(function(r){
    if(!r.error&&r.data) rules=r.data.rules||r.data;
    if(!rules) rules=empty;
    var prefs=(rules.allowed_dietary||[]).map(function(t){return prefMap[t]||t;});
    var blocked=rules.blocked_items||[];
    document.getElementById('frMaxPrice').textContent='¥'+(rules.max_price||35)+' / 餐';
    document.getElementById('frDietary').textContent=prefs.length?prefs.join('、'):'未设定';
    document.getElementById('frBlocked').textContent=blocked.length?blocked.join('、'):'无';
    document.getElementById('frNotify').textContent=rules.notify_on_unconfirm!==false?'开启（'+(rules.unconfirm_timeout_minutes||30)+'分钟）':'关闭';
    document.getElementById('frNotes').textContent=rules.notes||'无';
  });
}

PageManager.pageHooks.profile = { onEnter:function(){loadFamilyProfile();} };
// 已保存的饮食规则页：进入时加载规则数据
PageManager.pageHooks['family-rules'] = { onEnter:loadFamilyRules };

function init(){
  document.getElementById('profileMsgsBtn').addEventListener('click',function(){PageManager.navigate('messages');});
  document.getElementById('profileOrdersBtn').addEventListener('click',function(){PageManager.navigate('family-history');});
  // 点击"已保存的饮食规则" → 进入新页面
  document.getElementById('profileRulesBtn').addEventListener('click',function(){PageManager.navigate('family-rules');});
  document.getElementById('profileAnalysisBtn').addEventListener('click',function(){PageManager.navigate('analysis');});
  // 已保存的饮食规则页：返回 + 修改规则
  document.getElementById('familyRulesBack').addEventListener('click',function(){PageManager.back('profile');});
  document.getElementById('familyRulesModifyBtn').addEventListener('click',function(){PageManager.navigate('settings');});
  // 个人信息栏 → 个人信息编辑页
  var card=document.getElementById('familyElderCard');
  if(card) card.addEventListener('click',function(){ PageManager.navigate('family-edit'); });
  // Bottom nav
  document.querySelectorAll('#page-profile .nav-item').forEach(function(item){
    item.addEventListener('click',function(){
      var p=item.getAttribute('data-page');
      if(p==='status') PageManager.navigate('status');
      else if(p==='orders') PageManager.navigate('family-orders');
      else if(p==='profile') PageManager.navigate('profile');
    });
  });
}
init();
})();

// ==============================
// PAGE B-07: 个人信息编辑
// ==============================
(function(){
var DOM={};

function loadForm(){
  var saved=localStorage.getItem('familyProfile');
  var p=saved?JSON.parse(saved):{name:'女儿',age:35,gender:'女',phone:'13900008888',elder:'张奶奶',elderGender:'女'};
  DOM.name.value=p.name||'';
  DOM.age.value=p.age||'';
  DOM.gender.value=p.gender||'女';
  DOM.phone.value=p.phone||'';
  DOM.elder.value=p.elder||'';
  DOM.elderGender.value=p.elderGender||'女';
}
function saveProfile(){
  var name=DOM.name.value.trim();
  var age=DOM.age.value.trim();
  var gender=DOM.gender.value;
  var phone=DOM.phone.value.trim();
  var elder=DOM.elder.value.trim();
  var elderGender=DOM.elderGender.value;
  if(!name){ showToast('请输入姓名','error'); DOM.name.focus(); return; }
  if(age && (Number(age)<18||Number(age)>120)){ showToast('请输入合理的年龄（18-120）','error'); DOM.age.focus(); return; }
  if(phone && !/^1\d{10}$/.test(phone)){ showToast('请输入正确的11位手机号','error'); DOM.phone.focus(); return; }
  var profile={name:name, age:age?Number(age):'', gender:gender, phone:phone||'', elder:elder||'', elderGender:elderGender};
  localStorage.setItem('familyProfile',JSON.stringify(profile));
  showToast('个人信息已保存','success');
  PageManager.back('profile');
}
function goBack(){ PageManager.back('profile'); }

PageManager.pageHooks['family-edit'] = {
  onEnter: function(){ loadForm(); },
  onLeave: function(){}
};

function init(){
  DOM.name=document.getElementById('familyEditName');
  DOM.age=document.getElementById('familyEditAge');
  DOM.gender=document.getElementById('familyEditGender');
  DOM.phone=document.getElementById('familyEditPhone');
  DOM.elder=document.getElementById('familyEditElder');
  DOM.elderGender=document.getElementById('familyEditElderGender');
  document.getElementById('familyEditBack').addEventListener('click',goBack);
  document.getElementById('familyEditSaveBtn').addEventListener('click',saveProfile);
}
init();
})();

// ==============================
// PAGE B-09: 今日订单（当天全部订单）
// ==============================
(function(){
var DOM={};

function isToday(iso){
  if(!iso) return false;
  try{
    var d=new Date(iso), t=new Date();
    return d.getFullYear()===t.getFullYear()&&d.getMonth()===t.getMonth()&&d.getDate()===t.getDate();
  }catch(e){ return false; }
}
function fmtTime(iso){
  if(!iso) return '--';
  try{var d=new Date(iso);return d.getHours().toString().padStart(2,'0')+':'+d.getMinutes().toString().padStart(2,'0');}catch(e){return '--';}
}
function renderTodayOrders(orders){
  DOM.list.innerHTML='';
  if(!orders.length){ DOM.empty.style.display='flex'; DOM.count.style.display='none'; return; }
  DOM.empty.style.display='none';
  DOM.count.style.display='block';
  var d=new Date();
  DOM.count.textContent=(d.getMonth()+1)+'月'+d.getDate()+'日 · 共 '+orders.length+' 笔订单';
  var statusMap={created:'已下单',paid:'已支付',preparing:'制作中',delivering:'配送中',delivered:'已送达',confirmed:'已收餐',cancelled:'已取消',unconfirmed_timeout:'超时未确认'};
  orders.forEach(function(o){
    var card=document.createElement('div'); card.className='today-order-card';
    var st=statusMap[o.status]||o.status||'--';
    var stCls=(o.status==='cancelled'||o.status==='unconfirmed_timeout')?'too-status--cancel':(o.status==='delivered'||o.status==='confirmed')?'too-status--done':'';
    var rule=o.rule_passed!==false?'规则已通过':'需关注';
    var ruleCls=o.rule_passed!==false?'too-rule--pass':'too-rule--warn';
    card.innerHTML='<div class="too-top"><span class="too-meal">'+escapeHtml(o.meal_name||'餐品')+'</span><span class="too-status '+stCls+'">'+st+'</span></div>'
      +'<div class="too-bottom"><span class="too-price">¥'+((o.meal_price||0).toFixed(2))+'</span><span class="too-meta"><span class="too-rule '+ruleCls+'">'+rule+'</span><span class="too-time">'+fmtTime(o.created_at)+'</span></span></div>';
    DOM.list.appendChild(card);
  });
}
async function loadTodayOrders(){
  var r=await API.getFamilyOrders();
  var orders=[];
  if(!r.error&&Array.isArray(r.data)) orders=r.data.filter(function(o){return isToday(o.created_at);});
  renderTodayOrders(orders);
}
function escapeHtml(s){var d=document.createElement('div');d.textContent=s;return d.innerHTML;}

PageManager.pageHooks['family-orders'] = { onEnter:loadTodayOrders };

function init(){
  DOM.list=document.getElementById('familyOrdersList');
  DOM.empty=document.getElementById('familyOrdersEmpty');
  DOM.count=document.getElementById('familyOrdersCount');
  document.getElementById('familyOrdersBack').addEventListener('click',function(){PageManager.back('status');});
  document.querySelectorAll('#page-family-orders .nav-item').forEach(function(item){
    item.addEventListener('click',function(){
      var p=item.getAttribute('data-page');
      if(p==='status') PageManager.navigate('status');
      else if(p==='orders') PageManager.navigate('family-orders');
      else if(p==='profile') PageManager.navigate('profile');
    });
  });
}
init();
})();

// ==============================
// PAGE B-10: 订单记录（历史订单）
// ==============================
(function(){
var DOM={};

function fmtDateTime(iso){
  if(!iso) return '--';
  try{
    var d=new Date(iso);
    return (d.getMonth()+1)+'月'+d.getDate()+'日 '+d.getHours().toString().padStart(2,'0')+':'+d.getMinutes().toString().padStart(2,'0');
  }catch(e){ return '--'; }
}
function renderHistory(orders){
  DOM.list.innerHTML='';
  if(!orders.length){ DOM.empty.style.display='flex'; DOM.count.style.display='none'; return; }
  DOM.empty.style.display='none';
  DOM.count.style.display='block';
  DOM.count.textContent='共 '+orders.length+' 笔订单';
  var statusMap={created:'已下单',paid:'已支付',preparing:'制作中',delivering:'配送中',delivered:'已送达',confirmed:'已收餐',cancelled:'已取消',unconfirmed_timeout:'超时未确认'};
  orders.forEach(function(o){
    var card=document.createElement('div'); card.className='today-order-card';
    var st=statusMap[o.status]||o.status||'--';
    var stCls=(o.status==='cancelled'||o.status==='unconfirmed_timeout')?'too-status--cancel':(o.status==='delivered'||o.status==='confirmed')?'too-status--done':'';
    var rule=o.rule_passed!==false?'规则已通过':'需关注';
    var ruleCls=o.rule_passed!==false?'too-rule--pass':'too-rule--warn';
    card.innerHTML='<div class="too-top"><span class="too-meal">'+escapeHtml(o.meal_name||'餐品')+'</span><span class="too-status '+stCls+'">'+st+'</span></div>'
      +'<div class="too-bottom"><span class="too-price">¥'+((o.meal_price||0).toFixed(2))+'</span><span class="too-meta"><span class="too-rule '+ruleCls+'">'+rule+'</span><span class="too-time">'+fmtDateTime(o.created_at)+'</span></span></div>';
    DOM.list.appendChild(card);
  });
}
async function loadOrderHistory(){
  var r=await API.getFamilyOrders();
  var orders=[];
  if(!r.error&&Array.isArray(r.data)) orders=r.data;
  renderHistory(orders);
}
function escapeHtml(s){var d=document.createElement('div');d.textContent=s;return d.innerHTML;}

PageManager.pageHooks['family-history'] = { onEnter:loadOrderHistory };

function init(){
  DOM.list=document.getElementById('familyHistoryList');
  DOM.empty=document.getElementById('familyHistoryEmpty');
  DOM.count=document.getElementById('familyHistoryCount');
  document.getElementById('familyHistoryBack').addEventListener('click',function(){PageManager.back('profile');});
}
init();
})();

// ===== 启动 =====
PageManager.init();
console.log('👨‍👩‍👧 饭心 AI · 家属端 SPA 初始化完成');
})();
