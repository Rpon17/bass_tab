import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

function Search() {
  const [query, setQuery] = useState(''); 
  const [results, setResults] = useState([]);
  const navigate = useNavigate();

  // 검색 로직
  const handleSearch = async () => {
    if (!query.trim()) return; 

    try {
      // ✅ Render에 배포된 백엔드 주소로 변경!
      const response = await fetch(`https://bass-main-server.onrender.com/v1/songs/search?q=${query}`);
      const data = await response.json();

      // ✅ [중복 제거 로직 추가]
      // 제목(title)과 가수(artist)를 합친 문자열을 키(Key)로 사용하여 중복을 걸러냅니다.
      const uniqueResults = Array.from(
        new Map(data.map(song => [`${song.title}-${song.artist}`, song])).values()
      );

      setResults(uniqueResults);
    } catch (error) {
      console.error("검색 중 오류 발생:", error);
      alert("검색에 실패했습니다.");
    }
  };

  const goToPlayer = (song) => {
    navigate(`/player/${song.song_id}`, { state: { songData: song } });
  };

  return (
    <div style={{ padding: '20px', minHeight: '100vh', backgroundColor: '#fff' }}>
      
      {/* 🧭 네비게이션 바: 홈 버튼 및 뒤로가기 */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'flex-start', 
        gap: '20px', 
        marginBottom: '20px',
        borderBottom: '1px solid #eee',
        paddingBottom: '10px'
      }}>
        <button 
          onClick={() => navigate('/home')} 
          style={navButtonStyle}
        >
          🏠 Home
        </button>
        <button 
          onClick={() => navigate(-1)} 
          style={navButtonStyle}
        >
          ⬅️ Back
        </button>
      </div>

      <div style={{ textAlign: 'center' }}>
        <h2 style={{ marginBottom: '20px' }}>노래 검색</h2>
        
        {/* 검색창 영역 */}
        <div style={{ marginBottom: '30px' }}>
          <input 
            type="text" 
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()} 
            placeholder="노래 제목이나 가수를 입력하세요"
            style={{ 
              padding: '12px', 
              width: '300px', 
              borderRadius: '8px 0 0 8px', 
              border: '1px solid #ccc',
              outline: 'none'
            }}
          />
          <button 
            onClick={handleSearch} 
            style={{ 
              padding: '12px 20px', 
              cursor: 'pointer', 
              borderRadius: '0 8px 8px 0', 
              border: '1px solid #000',
              backgroundColor: '#000',
              color: '#fff',
              fontWeight: 'bold'
            }}
          >
            검색
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
                  <div style={{ 
                    fontSize: '0.85rem', 
                    padding: '5px 10px', 
                    borderRadius: '15px',
                    backgroundColor: song.status === 'done' ? '#eef2ff' : '#fff7ed',
                    color: song.status === 'done' ? '#4338ca' : '#c2410c',
                    border: `1px solid ${song.status === 'done' ? '#c7d2fe' : '#fdba74'}`
                  }}>
                    {song.status === 'done' ? '● 분석 완료' : '○ 분석 중...'}
                  </div>
                </div>
              </div>
            ))
          ) : (
            <div style={{ textAlign: 'center', marginTop: '50px' }}>
              <p style={{ color: '#999', fontSize: '1.1rem' }}>검색 결과가 없습니다.</p>
              <p style={{ color: '#999', fontSize: '0.7rem' }}>Don't stop believen!</p>
              <button 
                onClick={() => navigate('/create')}
                style={{ marginTop: '10px', color: '#0066cc', border: 'none', background: 'none', cursor: 'pointer', textDecoration: 'underline' }}
              >
                직접 악보 제작하기
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// 스타일 객체들
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

const itemStyle = {
  borderBottom: '1px solid #eee', 
  padding: '20px 15px', 
  cursor: 'pointer',
  transition: 'background 0.2s',
  backgroundColor: 'white'
};

export default Search;