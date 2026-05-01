import pathlib, re

html = pathlib.Path('static/dashboard.html').read_text(encoding='utf-8')

# 1. Add user email display to topbar
old_clock = '<div class="topbar-clock" id="tb-clock">--:--:--</div>'
new_clock = (
    '<div class="topbar-stat" id="tb-user" style="display:none">'
    '<span style="color:#22c55e">&#9679;</span>'
    '<span class="val" id="tb-email" style="font-size:11px;max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"></span>'
    '</div>'
    '<div class="topbar-divider"></div>'
    + old_clock
)
html = html.replace(old_clock, new_clock, 1)

# 2. Update loadStats JS to show user email from status.auth
old_model_line = "document.getElementById('tb-model').textContent = (status.provider||'?') + '/' + (status.model||'?').split('-').slice(-2).join('-');"
new_model_line = (
    "document.getElementById('tb-model').textContent = (status.provider||'?') + '/' + (status.model||'?').split('-').slice(-2).join('-');"
    "if(status.auth&&status.auth.signed_in){"
    "  const uEl=document.getElementById('tb-user');"
    "  const eEl=document.getElementById('tb-email');"
    "  if(uEl&&eEl){uEl.style.display='flex';eEl.textContent=status.auth.email||'signed in';}"
    "}"
)
html = html.replace(old_model_line, new_model_line, 1)

pathlib.Path('static/dashboard.html').write_text(html, encoding='utf-8')
print('Dashboard patched, size:', len(html))
print('User email in topbar:', 'tb-user' in html)
print('Auth check in JS:', 'status.auth' in html)
