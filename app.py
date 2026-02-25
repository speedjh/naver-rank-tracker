{% extends "base.html" %}
{% block title %}API 설정 - 네이버 순위 트래커{% endblock %}
{% block content %}

<div class="page-header">
  <div class="page-title">⚙️ 네이버 API 설정</div>
  <div class="page-sub">네이버 개발자 센터에서 발급받은 키를 입력하세요</div>
</div>

<div class="card" style="max-width:560px;">
  <div class="card-title">🔑 API 키 입력</div>
  <form action="/settings" method="post">
    <div style="margin-bottom:16px;">
      <label>Client ID *</label>
      <input type="text" name="client_id" value="{{ client_id }}" placeholder="Bl99m0KRtTXmQds2_i5e" required>
    </div>
    <div style="margin-bottom:20px;">
      <label>Client Secret *</label>
      <input type="password" name="client_secret" value="{{ client_secret }}" placeholder="mXDQnlETgk" required>
    </div>
    <button type="submit" class="btn btn-primary">💾 저장</button>
  </form>
</div>

<div class="card" style="max-width:560px;background:#1a2535;border:1px solid #2d3f5a;">
  <div class="card-title" style="color:#3b82f6;">ℹ️ API 발급 방법</div>
  <ol style="padding-left:20px;line-height:2;font-size:.875rem;color:#94a3b8;">
    <li><a href="https://developers.naver.com" target="_blank" style="color:#03c75a;">developers.naver.com</a> 접속</li>
    <li>로그인 → <strong style="color:#e2e8f0;">Application → 애플리케이션 등록</strong></li>
    <li>사용 API에서 <strong style="color:#e2e8f0;">"검색" 선택</strong></li>
    <li>등록 후 <strong style="color:#e2e8f0;">Client ID / Client Secret</strong> 복사</li>
    <li>하루 <strong style="color:#f59e0b;">25,000회</strong> 무료 호출 가능</li>
  </ol>
</div>

{% endblock %}
