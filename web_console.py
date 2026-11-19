"""Small, stateless authentication helpers and UI for the NEXORA mobile command console."""
import hashlib
import hmac
import time


SESSION_TTL_SECONDS = 8 * 60 * 60


def create_console_session(secret: str, now: int | None = None) -> str:
    if not isinstance(secret, str) or len(secret) < 16:
        raise ValueError("Console password must contain at least 16 characters")
    expires = int(now if now is not None else time.time()) + SESSION_TTL_SECONDS
    payload = str(expires)
    signature = hmac.new(secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).hexdigest()
    return payload + "." + signature


def verify_console_session(token: str, secret: str, now: int | None = None) -> bool:
    if not isinstance(secret, str) or len(secret) < 16 or not isinstance(token, str):
        return False
    try:
        expires_text, supplied_signature = token.split(".", 1)
        expires = int(expires_text)
    except (ValueError, TypeError):
        return False
    current = int(now if now is not None else time.time())
    if expires <= current or expires > current + SESSION_TTL_SECONDS:
        return False
    expected = hmac.new(
        secret.encode("utf-8"), expires_text.encode("ascii"), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(supplied_signature, expected)


CONSOLE_HTML = r"""<!doctype html>
<html lang="my">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#111827">
<title>NEXORA Command Console</title>
<style>
:root{color-scheme:dark;font-family:system-ui,-apple-system,sans-serif;background:#0b1020;color:#eef2ff}
*{box-sizing:border-box}body{margin:0;padding:22px 14px 40px;background:linear-gradient(150deg,#101a33,#090d18);min-height:100vh}
main{max-width:620px;margin:auto}.panel{background:#151e32;border:1px solid #2b3853;border-radius:18px;padding:20px;margin:14px 0;box-shadow:0 12px 32px #0004}
h1{font-size:24px;margin:0 0 6px}.muted{color:#aab7d1;font-size:14px;line-height:1.55}
label{display:block;font-size:14px;margin:15px 0 7px;color:#cbd5e1}
input,select,textarea,button{font:inherit;width:100%;border-radius:11px;padding:13px;border:1px solid #40506f;background:#0d1528;color:#f8fafc}
textarea{min-height:92px;resize:vertical}button{background:#2563eb;border:0;font-weight:700;margin-top:14px;cursor:pointer}
button.secondary{background:#334155}button:disabled{opacity:.55}
#result{white-space:pre-wrap;overflow-wrap:anywhere;background:#0b1222;border-radius:12px;padding:12px;min-height:54px;margin-top:14px;font-size:14px}
.hidden{display:none}.tag{display:inline-block;background:#1e3a5f;color:#bfdbfe;border-radius:20px;padding:4px 9px;font-size:12px;margin:8px 4px 0 0}
.top{display:flex;justify-content:space-between;align-items:center;gap:10px}
@media(min-width:560px){body{padding-top:42px}.panel{padding:26px}}
</style>
</head>
<body><main>
<section class="panel">
 <h1>NEXORA Command Console</h1>
 <div class="muted">ChatGPT ကရေးပေးသော command ကို ဒီနေရာတွင် ပို့နိုင်သည်။ Telegram Bot သို့ private chat တစ်ခုတည်းကိုသာ ပို့မည်။</div>
 <span class="tag">Mobile Friendly</span><span class="tag">HTTPS only</span><span class="tag">No API key in browser</span>
</section>
<section class="panel" id="loginPanel">
 <h2>လုံခြုံစွာ ဝင်ရောက်ရန်</h2>
 <div class="muted">Render Environment တွင် သတ်မှတ်မည့် NEXORA_CONSOLE_PASSWORD ကို ထည့်ပါ။ Telegram Bot Token သို့မဟုတ် Bridge API Key မဟုတ်ပါ။</div>
 <label for="password">Console Password</label>
 <input id="password" type="password" autocomplete="current-password" placeholder="Console password">
 <button id="loginBtn">ဝင်မည်</button><div id="loginResult" class="muted" role="status"></div>
</section>
<section class="panel hidden" id="commandPanel">
 <div class="top"><h2>Command ပို့ရန်</h2><button class="secondary" id="logoutBtn" style="width:auto;margin:0">ထွက်မည်</button></div>
 <label for="command">Command</label>
 <select id="command">
  <option>status</option><option>help</option><option>auto</option><option>seriesguide</option><option>create</option><option>research</option><option>draft3</option><option>allplatforms</option><option>voiceover3</option><option>render</option><option>animesynopsis</option><option>multisourceresearch</option><option>seriesresearch</option><option>animationepisodes</option><option>topratedepisodes</option><option>episodepack</option><option>episodeoutline</option><option>recapvideo</option><option>movieplotresearch</option><option>moviemultisourceresearch</option><option>growthpack</option><option>clipsource</option><option>autoplotclip</option><option>autoclip</option><option>autonarrateclip</option><option>autofactsclip</option>
 </select>
 <label for="argument">Argument (optional, one line, max 3500 characters)</label>
 <textarea id="argument" maxlength="3500" placeholder="ဥပမာ: Frieren: Beyond Journey's End"></textarea>
 <button id="sendBtn">Telegram သို့ ပို့မည်</button>
 <div id="result" role="status">Command မပို့ရသေးပါ။</div>
 <p class="muted">ပို့ပြီးကြောင်း ပြသခြင်းသည် Bot handler သို့ command dispatch ဖြစ်ကြောင်းသာ ဆိုလိုသည်။ Video ထုတ်ပြီးကြောင်း အာမခံခြင်းမဟုတ်ပါ။ Narration စာသားအများကြောင်းပါသော command များကို Telegram မှ တိုက်ရိုက်ပို့ပါ။</p>
</section>
</main>
<script>
const $=id=>document.getElementById(id);
fetch("/console/session",{credentials:"same-origin"}).then(r=>r.json()).then(s=>{if(s.authenticated){$("loginPanel").classList.add("hidden");$("commandPanel").classList.remove("hidden");}}).catch(()=>{});
async function api(path,data){
 const response=await fetch(path,{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json"},body:JSON.stringify(data||{})});
 const body=await response.json().catch(()=>({detail:"Invalid server response"}));
 if(!response.ok)throw new Error(body.detail||("HTTP "+response.status));
 return body;
}
$("loginBtn").addEventListener("click",async()=>{
 $("loginBtn").disabled=true;
 try{await api("/console/login",{password:$("password").value});$("password").value="";$("loginPanel").classList.add("hidden");$("commandPanel").classList.remove("hidden");$("result").textContent="ဝင်ရောက်ပြီးပါပြီ။";}
 catch(e){$("loginResult").textContent=e.message;$("loginPanel").classList.remove("hidden");}
 finally{$("loginBtn").disabled=false;}
});
$("password").addEventListener("keydown",e=>{if(e.key==="Enter")$("loginBtn").click();});
$("sendBtn").addEventListener("click",async()=>{
 const argument=$("argument").value.trim();
 if(argument.includes("\n")||argument.includes("\r")){$("result").textContent="Argument ကို တစ်ကြောင်းတည်း ထည့်ပါ။";return;}
 $("sendBtn").disabled=true;$("result").textContent="ပို့နေသည်...";
 try{const r=await api("/console/command",{command:$("command").value,argument});$("result").textContent="ပို့ပြီးပါပြီ: /"+r.command+"\nTelegram ထဲတွင် Bot ပြန်စာကို စစ်ပါ။";}
 catch(e){$("result").textContent=e.message;if(e.message==="Console login required"){$("commandPanel").classList.add("hidden");$("loginPanel").classList.remove("hidden");}}
 finally{$("sendBtn").disabled=false;}
});
$("logoutBtn").addEventListener("click",async()=>{try{await api("/console/logout",{});}catch(e){}$("commandPanel").classList.add("hidden");$("loginPanel").classList.remove("hidden");$("result").textContent="ထွက်ပြီးပါပြီ။";});
</script>
</body></html>"""
