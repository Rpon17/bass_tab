import { useEffect, useState, useRef, useMemo, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

function Player() {
  const location = useLocation();
  const navigate = useNavigate();
  const songData = location.state?.songData;

  const [tabData, setTabData] = useState([]);
  const [currentTime, setCurrentTime] = useState(0);
  
  // 오디오 모드 4종 & 악보 모드 2종
  const [audioMode, setAudioMode] = useState('original_audio_path');
  const [tabMode, setTabMode] = useState('original_tab_path');
  
  const [isAudioMenuOpen, setIsAudioMenuOpen] = useState(false);
  
  const audioRef = useRef(null);
  const currentBarRef = useRef(null);

  const API_BASE_URL = 'https://rpon17-bass-project-main.onrender.com';

  const getFullUrl = (path) => {
    if (!path) return null;
    let cleanPath = path.trim();
    if (cleanPath.includes('/asset/') && !cleanPath.includes('/assets/')) {
      cleanPath = cleanPath.replace('/asset/', '/assets/');
    }
    if (cleanPath.startsWith('http')) return cleanPath;
    if (cleanPath.includes('supabase.co')) return `https://${cleanPath}`;
    return `${API_BASE_URL}${cleanPath.startsWith('/') ? '' : '/'}${cleanPath}`;
  };

  useEffect(() => {
    const tabUrl = getFullUrl(songData?.[tabMode]);
    if (tabUrl) {
      fetch(tabUrl)
        .then(res => res.json())
        .then(data => setTabData(Array.isArray(data) ? data : data.bars || []))
        .catch(() => setTabData([]));
    }
  }, [songData, tabMode]);

  // 자동 스크롤 기능 유지
  useEffect(() => {
    if (currentBarRef.current) {
      currentBarRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [currentTime]);

  // 📍 2. 마디 클릭 시 해당 시간으로 이동하는 함수
  const handleBarClick = useCallback((startTime) => {
    if (audioRef.current && startTime !== undefined) {
      // 오디오 플레이어의 현재 시간을 마디 시작 시간으로 설정
      audioRef.current.currentTime = startTime;
      
      // 혹시 정지 상태라면 바로 재생 시작
      if (audioRef.current.paused) {
        audioRef.current.play().catch(error => {
          console.error("오디오 자동 재생 실패:", error);
          // 브라우저 보안 정책으로 자동 재생이 막힌 경우 사용자에게 알림을 주거나 추가 처리 필요
        });
      }
    }
  }, []);

  const renderSingleBar = (bar, isCurrent) => {
    if (!bar) return <div style={{ flex: 1, height: '110px' }}></div>;
    const lines = [0, 1, 2, 3]; // 4현 베이스
    let barCanvas = {};
    lines.forEach(l => barCanvas[l] = Array(16).fill("-"));
    
    bar.notes?.forEach((note) => {
      if (note.line > 3) return;
      const fret = note.fret.toString();
      let pos = Math.round(note.offset * 4);
      if (pos > 15) pos = 15;
      if (fret.length > 1) {
        barCanvas[note.line][pos] = fret[0];
        if (pos + 1 < 16) barCanvas[note.line][pos + 1] = fret[1];
      } else {
        barCanvas[note.line][pos] = fret;
      }
    });

    return (
      <div 
        ref={isCurrent ? currentBarRef : null} 
        key={`bar-${bar.bar_index}`}
        // 📍 2. 마디 전체 영역에 클릭 이벤트 연결
        onClick={() => handleBarClick(bar.start_time)}
        style={{ 
          ...barStyle,
          backgroundColor: isCurrent ? 'rgba(0, 0, 0, 0.05)' : 'transparent',
          cursor: 'pointer' // 마우스 올렸을 때 클릭 가능하다는 표시
        }}
      >
        <pre style={tabTextStyle}>
          {lines.map(l => (
            <div key={l} style={{ height: '22px' }}>
              {barCanvas[l].join('')}
              <span style={{ color: '#ccc', marginLeft: '5px' }}>
                {bar.bar_index % 4 === 3 ? '' : '|'}
              </span>
            </div>
          ))}
        </pre>
      </div>
    );
  };

  const chunkedBars = useMemo(() => {
    const chunks = [];
    for (let i = 0; i < tabData.length; i += 4) chunks.push(tabData.slice(i, i + 4));
    return chunks;
  }, [tabData]);

  if (!songData) return <div style={errorPageStyle}>곡 정보를 찾을 수 없습니다.</div>;

  return (
    <div style={containerStyle}>
      {/* 🧭 1. Glassmorphism Header 및 이모지 버튼 복구 */}
      <header style={headerStyle}>
        <div style={{ display: 'flex', gap: '15px' }}>
          {/* 사진처럼 디자인 복구한 Home 버튼 */}
          <button onClick={() => navigate('/home')} style={imageButtonStyle}>
            <span style={{ fontSize: '1.2rem' }}>🏠</span> <span style={btnTextStyle}>Home</span>
          </button>
          
          {/* 사진처럼 디자인 복구한 Back 버튼 */}
          <button onClick={() => navigate(-1)} style={imageButtonStyle}>
            <span style={{ fontSize: '1.2rem' }}>⬅️</span> <span style={btnTextStyle}>Back</span>
          </button>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          {/* 오디오 선택 */}
          <div style={{ position: 'relative' }}>
            <button onClick={() => setIsAudioMenuOpen(!isAudioMenuOpen)} style={selectButtonStyle}>
              🎵 AUDIO: {audioMode.replace('_path', '').toUpperCase()} ▾
            </button>
            {isAudioMenuOpen && (
              <div style={dropdownStyle}>
                {['original_audio_path', 'bass_only_path', 'bass_boosted_path', 'bass_removed_path'].map(k => (
                  <div key={k} onClick={() => {setAudioMode(k); setIsAudioMenuOpen(false);}} style={dropdownItemStyle}>{k.replace('_path', '').replace('_', ' ').toUpperCase()}</div>
                ))}
              </div>
            )}
          </div>
          {/* 악보 선택 */}
          <button onClick={() => setTabMode(tabMode === 'original_tab_path' ? 'root_tab_path' : 'original_tab_path')} style={selectButtonStyle}>
            🎼 TAB: {tabMode === 'original_tab_path' ? 'ORIGINAL' : 'ROOT'}
          </button>
        </div>
      </header>

      {/* 🎸 악보 영역 (마디 구분선 제거된 4마디 1줄 레이아웃) */}
      <main style={mainContentStyle}>
        <div>
          <h1 style={titleStyle}>{songData.title}</h1>
          <p style={artistStyle}>{songData.artist}</p>
        </div>

        {chunkedBars.map((group, gIdx) => (
          <div key={gIdx} style={rowStyle}>
            {/* 박자표 */}
            <div style={timeSigStyle}>4<br/>4</div>
            {/* 4마디 묶음 상자 */}
            <div style={barGroupStyle}>
              {group.map(bar => renderSingleBar(bar, currentTime >= bar.start_time && currentTime < bar.end_time))}
              {/* 4마디가 안되는 마지막 줄 빈 공간 채우기 */}
              {group.length < 4 && Array(4 - group.length).fill(null).map((_, i) => <div key={`empty-${i}`} style={{ flex: 1, minWidth: '220px', height: '110px' }}></div>)}
            </div>
          </div>
        ))}
      </main>

      {/* 🔊 오디오 플레이어 (하단 고정) */}
      <footer style={footerStyle}>
        <audio 
          ref={audioRef} 
          src={getFullUrl(songData?.[audioMode])} 
          controls 
          onTimeUpdate={() => setCurrentTime(audioRef.current.currentTime)}
          crossOrigin="anonymous" // CORS 문제 방지
          style={{ width: '100%', height: '40px' }}
        />
      </footer>
    </div>
  );
}

// --- ✨ UI 스타일 정의 ---
const containerStyle = { backgroundColor: '#fff', color: '#000', minHeight: '100vh', paddingBottom: '100px', fontFamily: 'sans-serif' };

// Glassmorphism Header 스타일
const headerStyle = { 
  position: 'sticky', top: 0, 
  display: 'flex', justifyContent: 'space-between', alignItems: 'center', 
  padding: '15px 30px', 
  backgroundColor: 'rgba(255, 255, 255, 0.8)', 
  backdropFilter: 'blur(8px)', 
  borderBottom: '1px solid #eee', 
  zIndex: 1000 
};

// 📍 이미지처럼 복구한 버튼 스타일 (옅은 회색 배경, 동그란 모서리)
const imageButtonStyle = { 
  display: 'flex', alignItems: 'center', gap: '8px', 
  padding: '10px 20px', 
  backgroundColor: '#f5f5f5', 
  border: 'none', 
  borderRadius: '12px', 
  cursor: 'pointer',
  transition: 'background 0.2s',
  hover: { backgroundColor: '#ebebeb' } // React inline style에서는 동작하지 않음, 필요시 마우스이벤트 추가
};
const btnTextStyle = { fontWeight: '700', fontSize: '1rem', color: '#000', letterSpacing: '-0.5px' };

const selectButtonStyle = { padding: '8px 16px', fontSize: '0.9rem', fontWeight: '700', cursor: 'pointer', border: 'none', borderRadius: '20px', backgroundColor: '#e0e0e0', color: '#000' };
const dropdownStyle = { position: 'absolute', top: '110%', right: 0, backgroundColor: '#fff', borderRadius: '10px', overflow: 'hidden', width: '180px', zIndex: 1100, border: '1px solid #eee', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' };
const dropdownItemStyle = { padding: '12px 15px', cursor: 'pointer', fontSize: '0.8rem', borderBottom: '1px solid #f0f0f0', color: '#333' };

const mainContentStyle = { maxWidth: '1000px', margin: '30px auto', padding: '0 20px' };
const titleStyle = { fontSize: '1.4rem', margin: '0 0 5px 0', fontWeight: '800' };
const artistStyle = { fontSize: '0.9rem', margin: '0 0 30px 0', color: '#666' };

const rowStyle = { display: 'flex', marginBottom: '40px', alignItems: 'center' };
// 박자표 스타일
const timeSigStyle = { fontSize: '24px', fontWeight: 'bold', marginRight: '15px', textAlign: 'center', lineHeight: '1', color: '#333' };
// 4마디를 묶는 전체 상자 (세로 구분선 없음)
const barGroupStyle = { display: 'flex', flex: 1, borderTop: '2px solid #333', borderBottom: '2px solid #333' };
// 개별 마디 스타일 (세로 구분선 제거, flex 속성으로 등분)
const barStyle = { flex: 1, minWidth: '220px', padding: '15px 10px', transition: 'background-color 0.2s', borderRadius: '4px', position: 'relative' };
const tabTextStyle = { margin: 0, fontFamily: '"Courier New", Courier, monospace', fontSize: '1.3rem', fontWeight: 'bold', letterSpacing: '2px', lineHeight: '1.2', color: '#333' };

const footerStyle = { position: 'fixed', bottom: 0, width: '100%', padding: '15px 30px', backgroundColor: '#f9f9f9', borderTop: '1px solid #eee', zIndex: 900 };
const errorPageStyle = { display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', color: '#aaa' };

export default Player;