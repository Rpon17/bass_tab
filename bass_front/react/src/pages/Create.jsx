import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

function Create() {
  const navigate = useNavigate();
  
  // 1. 상태 관리: input의 name 속성과 formData의 키값이 일치해야 함
  const [formData, setFormData] = useState({
    youtube_url: '',
    title: '',
    artist: ''
  });

  const [isLoading, setIsLoading] = useState(false);

  // 2. 입력 핸들러
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData({
      ...formData,
      [name]: value
    });
  };

  // 3. 폼 제출 핸들러 (중복 방지 로직 포함)
  const handleSubmit = async (e) => {
    e.preventDefault();

    // [중복 방지] 이미 요청 중이면 함수 실행 중단
    if (isLoading) return; 

    setIsLoading(true);

    try {
      // ✅ Render에 배포된 백엔드 주소로 변경!
      const response = await fetch('https://bass-main-server.onrender.com', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json' 
        },
        body: JSON.stringify(formData),
      });

      if (response.status === 201 || response.ok) {
        alert("악보 생성이 요청되었습니다! (Job ID 발급 완료)");
        
        // [중복 방지] 성공 후 입력 폼 초기화
        setFormData({ youtube_url: '', title: '', artist: '' });
        
        // 생성 후 검색 리스트 페이지로 이동
        navigate('/search'); 
      } else {
        const errorDetail = await response.json();
        alert(`생성 실패: ${errorDetail.detail || "서버 오류"}`);
      }
    } catch (error) {
      console.error("통신 오류:", error);
      alert("서버 연결에 실패했습니다. Render 서버가 켜져 있는지 확인하세요.");
    } finally {
      // 요청 완료 후 로딩 상태 해제
      setIsLoading(false);
    }
  };

  return (
    <div style={{ padding: '20px', backgroundColor: 'white', minHeight: '100vh' }}>
      
      {/* 상단 네비게이션 */}
      <div style={{ display: 'flex', gap: '15px', marginBottom: '30px' }}>
        <button onClick={() => navigate('/home')} style={btnStyle}>🏠 Home</button>
        <button onClick={() => navigate(-1)} style={btnStyle}>⬅️ Back</button>
      </div>

      <div style={{ maxWidth: '450px', margin: '0 auto', border: '1px solid #ddd', padding: '30px', borderRadius: '15px', boxShadow: '0 4px 6px rgba(0,0,0,0.1)' }}>
        <h2 style={{ textAlign: 'center', marginBottom: '20px' }}>🎸 새로운 악보 제작</h2>
        <p style={{ fontSize: '0.9rem', color: '#666', textAlign: 'center', marginBottom: '25px' }}>
          유튜브 링크를 기반으로 AI가 베이스 악보를 생성합니다.
        </p>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          
          <div>
            <label style={labelStyle}>YouTube URL</label>
            <input 
              name="youtube_url" 
              type="url"
              placeholder="https://www.youtube.com/watch?v=..."
              value={formData.youtube_url} 
              onChange={handleChange} 
              style={inputStyle} 
              required 
            />
          </div>

          <div>
            <label style={labelStyle}>노래 제목</label>
            <input 
              name="title" 
              type="text"
              placeholder="노래 제목을 입력하세요"
              value={formData.title} 
              onChange={handleChange} 
              style={inputStyle} 
              required 
            />
          </div>

          <div>
            <label style={labelStyle}>아티스트</label>
            <input 
              name="artist" 
              type="text"
              placeholder="아티스트(가수) 이름을 입력하세요"
              value={formData.artist} 
              onChange={handleChange} 
              style={inputStyle} 
              required 
            />
          </div>

          <button 
            type="submit" 
            disabled={isLoading} 
            style={{
              ...submitStyle,
              backgroundColor: isLoading ? '#999' : '#000',
              cursor: isLoading ? 'not-allowed' : 'pointer'
            }}
          >
            {isLoading ? 'AI 분석 요청 중...' : '악보 생성 시작하기'}
          </button>
        </form>
      </div>
    </div>
  );
}

// 스타일 정의
const labelStyle = { display: 'block', marginBottom: '5px', fontWeight: 'bold', fontSize: '0.9rem' };
const inputStyle = { width: '100%', padding: '12px', boxSizing: 'border-box', border: '1px solid #ccc', borderRadius: '8px', outline: 'none' };
const btnStyle = { padding: '8px 15px', cursor: 'pointer', border: '1px solid #000', borderRadius: '5px', backgroundColor: '#fff', fontSize: '0.9rem' };
const submitStyle = { padding: '15px', color: 'white', border: 'none', borderRadius: '8px', fontWeight: 'bold', fontSize: '1rem', marginTop: '10px', transition: 'background 0.3s' };

export default Create;