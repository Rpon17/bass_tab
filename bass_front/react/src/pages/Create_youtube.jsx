import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

function CreateYoutube() {
  const navigate = useNavigate();
  
  const [formData, setFormData] = useState({
    youtube_url: '',
    title: '',
    artist: ''
  });

  const [isLoading, setIsLoading] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData({ ...formData, [name]: value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isLoading) return; 
    setIsLoading(true);

    try {
      const response = await fetch('https://rpon17-bass-project-main.onrender.com/v1/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });

      if (response.ok) {
        navigate('/waiting'); 
      } else {
        const errorDetail = await response.json();
        alert(`생성 실패: ${errorDetail.detail || "서버 오류"}`);
      }
    } catch (error) {
      console.error("통신 오류:", error);
      alert("서버 연결에 실패했습니다.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ padding: '40px 20px', textAlign: 'center', minHeight: '100vh', backgroundColor: '#fff' }}>
      
      {/* 상단 네비게이션 - 이전 페이지와 동일한 간격과 스타일 */}
      <div style={{ display: 'flex', justifyContent: 'flex-start', gap: '15px', marginBottom: '30px' }}>
        <button onClick={() => navigate('/home')} style={btnStyle}>🏠 Home</button>
        <button onClick={() => navigate('/create')} style={btnStyle}>⬅️ Back</button>
      </div>

      {/* 제목 - Create 페이지와 동일한 두께와 크기 */}
      <h2 style={{ marginBottom: '50px', fontSize: '2.2rem', fontWeight: 'bold' }}>
        📺 유튜브로 제작
      </h2>

      <div style={formCardStyle}>
        <p style={{ fontSize: '1.1rem', color: '#555', marginBottom: '30px', lineHeight: '1.5' }}>
          유튜브 링크를 기반으로 AI가<br/>베이스 악보를 생성합니다.
        </p>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '25px', textAlign: 'left' }}>
          
          <div>
            <label style={labelStyle}>YouTube URL</label>
            <input 
              name="youtube_url" 
              type="url"
              placeholder="https://youtube.com/..."
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
              placeholder="아티스트 이름을 입력하세요"
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
              backgroundColor: isLoading ? '#ccc' : '#000', // 검정색 버튼으로 통일감을 주거나 유튜브 레드 선택
              cursor: isLoading ? 'not-allowed' : 'pointer'
            }}
          >
            {isLoading ? 'AI 분석 요청 중...' : '분석 시작하기'}
          </button>
        </form>
      </div>
    </div>
  );
}

// --- 스타일 객체 수정 (Create 페이지와 싱크 맞춤) ---

const btnStyle = { 
  padding: '8px 15px', 
  cursor: 'pointer', 
  border: '1px solid #000', 
  borderRadius: '8px', 
  backgroundColor: '#f5f5f5', 
  fontSize: '0.9rem',
  fontWeight: 'bold' // 글씨 두께 통일
};

const formCardStyle = {
  maxWidth: '500px',
  margin: '0 auto',
  padding: '50px 40px',
  border: '2px solid #000', // 굵은 테두리로 통일
  borderRadius: '30px',     // 둥근 모서리 통일
  backgroundColor: '#fff',
  boxShadow: 'none'         // 깔끔하게 테두리만 강조
};

const labelStyle = { 
  display: 'block', 
  marginBottom: '8px', 
  fontWeight: 'bold', 
  fontSize: '1rem' 
};

const inputStyle = { 
  width: '100%', 
  padding: '15px', 
  boxSizing: 'border-box', 
  border: '1px solid #000', // 입력창도 검정 테두리
  borderRadius: '12px', 
  outline: 'none',
  fontSize: '1rem'
};

const submitStyle = { 
  padding: '18px', 
  color: 'white', 
  border: 'none', 
  borderRadius: '15px', 
  fontWeight: 'bold', 
  fontSize: '1.2rem', 
  marginTop: '10px',
  transition: 'transform 0.2s ease'
};

export default CreateYoutube;