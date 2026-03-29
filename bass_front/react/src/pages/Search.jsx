import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import waitingImg1 from '../images/찾는거위.jpg';

function Search() {
  const [query, setQuery] = useState(''); 
  const [results, setResults] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  const API_BASE_URL = "https://rpon17-bass-project-main.onrender.com";

  const handleSearch = async () => {
    if (!query.trim()) return; 

    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/v1/songs/search?q=${encodeURIComponent(query)}`);
      
      if (!response.ok) {
        throw new Error('서버 응답에 문제가 있습니다.');
      }

      const data = await response.json();

      const uniqueResults = Array.from(
        new Map(data.map(song => [`${song.title}-${song.artist}`, song])).values()
      );

      setResults(uniqueResults);
    } catch (error) {
      console.error("검색 중 오류 발생:", error);
      alert("백엔드 서버와 연결할 수 없습니다. 잠시 후 다시 시도해주세요.");
    } finally {
      setIsLoading(false);
    }
  };

  const goToPlayer = (song) => {
    navigate(`/player/${song.song_id}`, { state: { songData: song } });
  };

  return (
    <div style={{ padding: '20px', minHeight: '100vh', backgroundColor: '#fff' }}>
      
      {/* 🧭 네비게이션 바 */}
      <div style={navBarInnerStyle}>
        <button onClick={() => navigate('/home')} style={navButtonStyle}>🏠 Home</button>
        <button onClick={() => navigate(-1)} style={navButtonStyle}>⬅️ Back</button>
      </div>

      <div style={{ textAlign: 'center' }}>
        
        {/* 검색창 영역 */}
        <div style={{ marginBottom: '20px', display: 'flex', justifyContent: 'center' }}>
          <input 
            type="text" 
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()} 
            placeholder="노래 제목이나 가수를 입력하세요"
            style={inputStyle}
          />
          <button 
            onClick={handleSearch} 
            disabled={isLoading}
            style={searchButtonStyle}
          >
            {isLoading ? '...' : '검색'}
          </button>
        </div>

        {/* 리스트 및 안내 영역 */}
        <div style={{ display: 'inline-block', textAlign: 'left', width: '100%', maxWidth: '500px' }}>
          {results.length > 0 ? (
            results.map((song) => (
              <div 
                key={song.song_id} 
                onClick={() => goToPlayer(song)}
                style={itemStyle}
                onMouseOver={(e) => e.currentTarget.style.background = '#f9f9f9'}
                onMouseOut={(e) => e.currentTarget.style.background = 'white'}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontWeight: 'bold', fontSize: '1.1rem', color: '#333' }}>{song.title}</div>
                    <div style={{ fontSize: '0.9rem', color: '#666', marginTop: '3px' }}>{song.artist}</div>
                  </div>
                  
                  <div style={{ 
                    ...statusBadgeStyle,
                    backgroundColor: (song.status === 'done' || song.status === 'SUCCESS') ? '#eef2ff' : '#fff7ed',
                    color: (song.status === 'done' || song.status === 'SUCCESS') ? '#4338ca' : '#c2410c',
                    border: `1px solid ${(song.status === 'done' || song.status === 'SUCCESS') ? '#c7d2fe' : '#fdba74'}`
                  }}>
                    {(song.status === 'done' || song.status === 'SUCCESS') ? '● 분석 완료' : '○ 분석 중...'}
                  </div>
                </div>
              </div>
            ))
          ) : (
            !isLoading && (
              <div style={{ textAlign: 'center', marginTop: '10px' }}>
                {/* 검색바와 밀착된 문구 */}
                <p style={{ color: '#100', fontSize: '1.1rem', marginBottom: '10px' }}>
                  거위가 악보리스트를 찾고있습니다
                </p>

                {/* 거위 이미지 - 아래 문구와 멀어지도록 marginBottom을 크게 설정 */}
                <img 
                  src={waitingImg1}
                  alt="Goose looking for tabs"
                  style={{ 
                    width: '400px',    
                    height: 'auto', 
                    borderRadius: '15px',
                    marginBottom: '60px' 
                  }} 
                />

                {/* 하단 버튼 그룹 - 서로 가깝게 배치 */}
                <p style={{ color: '#99', fontSize: '1.1rem', marginBottom: '5px' }}>
                  찾는 노래가 없다면?
                </p>
                <button 
                  onClick={() => navigate('/create')}
                  style={createLinkStyle}
                >
                  거위와 악보 만들러가기
                </button>
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
}

// --- 스타일 객체 ---
const navBarInnerStyle = {
  display: 'flex', 
  justifyContent: 'flex-start', 
  gap: '20px', 
  marginBottom: '20px',
  borderBottom: '1px solid #eee',
  paddingBottom: '10px'
};

const navButtonStyle = {
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  fontSize: '0.95rem',
  display: 'flex',
  alignItems: 'center',
  gap: '5px',
  padding: '8px 12px',
  borderRadius: '8px',
  backgroundColor: '#f5f5f5',
  fontWeight: 'bold'
};

const inputStyle = { 
  padding: '12px', 
  width: '300px', 
  borderRadius: '8px 0 0 8px', 
  border: '1px solid #ccc',
  outline: 'none'
};

const searchButtonStyle = { 
  padding: '12px 20px', 
  cursor: 'pointer', 
  borderRadius: '0 8px 8px 0', 
  border: '1px solid #000',
  backgroundColor: '#000',
  color: '#fff',
  fontWeight: 'bold',
  minWidth: '80px'
};

const itemStyle = {
  borderBottom: '1px solid #eee', 
  padding: '20px 15px', 
  cursor: 'pointer',
  transition: 'background 0.2s',
  backgroundColor: 'white'
};

const statusBadgeStyle = {
  fontSize: '0.85rem', 
  padding: '5px 10px', 
  borderRadius: '15px',
};

const createLinkStyle = { 
  color: '#0066cc', 
  border: 'none', 
  background: 'none', 
  cursor: 'pointer', 
  textDecoration: 'underline',
  fontSize: '1rem'
};

export default Search;