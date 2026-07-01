// Supabase 연결 설정 — 프로젝트 생성 후 두 값을 채우세요.
// 대시보드 → Project Settings → API:  Project URL / anon public key
// ⚠ anon key는 공개되어도 안전(RLS로 보호). service_role 키·DB비번은 절대 넣지 마세요.
window.SUPABASE_URL = "https://YOUR-PROJECT-REF.supabase.co";
window.SUPABASE_ANON_KEY = "YOUR-ANON-PUBLIC-KEY";

// 로그인 매핑: 아이디 'planit' → 이메일 'planit@planit.institute'
// (Supabase Auth는 이메일 기반. 사용자/비번 변경은 대시보드 Authentication에서.)
window.LOGIN_EMAIL_DOMAIN = "planit.institute";
