import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

function Search() {
  const [query, setQuery] = useState(''); 
  const [results, setResults] = useState([]);
  const [isLoading, setIsLoading] = useState(false); // 로딩 상태 관리
  const navigate = useNavigate();

  const API_BASE_URL = "https://rpon17-bass-project-main.onrender.com";

  // 검색 로직
  const handleSearch = async () => {
    if (!query.trim()) return; 

    setIsLoading(true); // 검색 시작 시 로딩 표시
    try {
      // ✅ 검색어 인코딩 처리 및 API 호출
      const response = await fetch(`${API_BASE_URL}/v1/songs/search?q=${encodeURIComponent(query)}`);
      
      if (!response.ok) {
        throw new Error('서버 응답에 문제가 있습니다.');
      }

      const data = await response.json();

      // ✅ 중복 제거 로직 (제목-가수 조합)
      const uniqueResults = Array.from(
        new Map(data.map(song => [`${song.title}-${song.artist}`, song])).values()
      );

      setResults(uniqueResults);
    } catch (error) {
      console.error("검색 중 오류 발생:", error);
      alert("백엔드 서버와 연결할 수 없습니다. 잠시 후 다시 시도해주세요.");
    } finally {
      setIsLoading(false); // 로딩 종료
    }
  };

  const goToPlayer = (song) => {
    // 분석이 완료된 곡만 플레이어로 보낼지, 혹은 진행 중인 곡도 보낼지 결정 가능
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
        <h2 style={{ marginBottom: '20px' }}>노래 검색</h2>
        
        {/* 검색창 영역 */}
        <div style={{ marginBottom: '30px', display: 'flex', justifyContent: 'center' }}>
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

        {/* 리스트 출력 영역 */}
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
                  
                  {/* ✅ 상태값에 따른 뱃지 (DB 값에 따라 'done' 또는 'SUCCESS' 등으로 수정 필요) */}
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
              <div style={{ textAlign: 'center', marginTop: '50px' }}>
                <p style={{ color: '#999', fontSize: '1.1rem' }}>검색 결과가 없습니다.</p>
                <p style={{ color: '#999', fontSize: '0.7rem' }}>새로운 곡을 추가해보세요!</p>
                <button 
                  onClick={() => navigate('/create')}
                  style={createLinkStyle}
                >
                  직접 악보 제작하기
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
  marginTop: '10px', 
  color: '#0066cc', 
  border: 'none', 
  background: 'none', 
  cursor: 'pointer', 
  textDecoration: 'underline' 
};

export default Search;