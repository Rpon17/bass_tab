import { useEffect, useState, useRef, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

function Player() {
  const location = useLocation();
  const navigate = useNavigate();
  const songData = location.state?.songData; // Search 페이지에서 전달받은 데이터

  const [tabData, setTabData] = useState(null);
  const [currentTime, setCurrentTime] = useState(0);
  
  const [audioMode, setAudioMode] = useState('original_audio_path');
  const [tabMode, setTabMode] = useState('original_tab_path');
  
  const [isAudioMenuOpen, setIsAudioMenuOpen] = useState(false);
  const [isTabMenuOpen, setIsTabMenuOpen] = useState(false);
  
  const audioRef = useRef(null);
  const currentBarRef = useRef(null);

  // ✅ 백엔드 베이스 URL (상대 경로일 경우 대비)
  const API_BASE_URL = 'https://bass-main-server.onrender.com';

  // ✅ [Helper] 주소 결합 로직: 전체 URL이면 그대로, 상대 경로면 서버 주소 결합
  const getFullUrl = (path) => {
    if (!path) return null;
    if (path.startsWith('http')) return path; 
    return `${API_BASE_URL}${path.startsWith('/') ? '' : '/'}${path}`;
  };

  // ✅ 1. JSON 악보 데이터 로드
  useEffect(() => {
    const targetPath = songData?.[tabMode];
    const tabUrl = getFullUrl(targetPath);

    if (tabUrl) {
      fetch(tabUrl)
        .then(res => {
          if (!res.ok) throw new Error("악보 파일을 찾을 수 없습니다.");
          return res.json();
        })
        .then(setTabData)
        .catch(err => {
          console.error("Tab load error:", err);
          setTabData([]); // 에러 시 빈 배열로 초기화하여 렌더링 깨짐 방지
        });
    }
  }, [songData, tabMode]);

  // ✅ 2. 현재 재생 바(Bar)로 스크롤 이동
  useEffect(() => {
    if (currentBarRef.current) {
      currentBarRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [currentTime]);

  const handleTimeUpdate = () => {
    if (audioRef.current) setCurrentTime(audioRef.current.currentTime);
  };

  const audioOptions = [
    { key: 'original_audio_path', label: 'Original Audio' },
    { key: 'bass_only_path', label: 'Bass Only' },
    { key: 'bass_boosted_path', label: 'Bass Boosted' },
    { key: 'bass_removed_path', label: 'Bass Removed' }
  ];

  const tabOptions = [
    { key: 'original_tab_path', label: 'Original Tab' },
    { key: 'root_tab_path', label: 'Root Tab' }
  ];

  // ✅ 3. 마디 렌더링 로직 (기존 유지)
  const renderSingleBar = (bar, isCurrent) => {
    if (!bar) return null;
    let barCanvas = { 0: "-".repeat(16), 1: "-".repeat(16), 2: "-".repeat(16), 3: "-".repeat(16) };
    
    bar.notes?.forEach((note) => {
      const line = note.line;
      if (line < 0 || line > 3) return;
      const fret = note.fret.toString();
      let position = Math.max(0, Math.min(15, Math.floor((note.offset / 4) * 15)));
      let arr = barCanvas[line].split('');
      arr[position] = fret;
      barCanvas[line] = arr.join('');
    });

    return (
      <div 
        ref={isCurrent ? currentBarRef : null} 
        key={bar.start_time}
        style={{ 
          flex: '1 1 0px', 
          minWidth: '0',
          padding: '10px 0', 
          borderRight: '1.5px solid black', 
          backgroundColor: isCurrent ? 'rgba(255, 255, 0, 0.3)' : 'transparent',
          position: 'relative'
        }}
      >
        <pre style={{ margin: 0, lineHeight: '1.2', fontSize: '1.1rem', fontWeight: 'bold', fontFamily: 'monospace', textAlign: 'center' }}>
          {barCanvas[0]}<br/>{barCanvas[1]}<br/>{barCanvas[2]}<br/>{barCanvas[3]}
        </pre>
      </div>
    );
  };

  // ✅ 4. 데이터 그룹화 및 현재 소스 계산 (성능 최적화)
  const chunkedBars = useMemo(() => {
    const chunks = [];
    if (tabData && Array.isArray(tabData)) {
      for (let i = 0; i < tabData.length; i += 4) chunks.push(tabData.slice(i, i + 4));
    }
    return chunks;
  }, [tabData]);

  const currentAudioSrc = useMemo(() => getFullUrl(songData?.[audioMode]), [songData, audioMode]);

  // 데이터 없을 시 예외 처리
  if (!songData) return (
    <div style={{padding: '50px', textAlign: 'center'}}>
      <p>곡 정보가 없습니다.</p>
      <button onClick={() => navigate('/home')}>검색으로 돌아가기</button>
    </div>
  );

  // --- 스타일 정의 ---
  const navButtonStyle = {
    background: 'none', border: 'none', cursor: 'pointer', fontSize: '1rem',
    display: 'flex', alignItems: 'center', gap: '5px', padding: '5px 10px',
    borderRadius: '5px', backgroundColor: '#f0f0f0', fontWeight: 'bold'
  };

  const menuButtonStyle = {
    padding: '8px 16px', backgroundColor: '#fff', border: '1px solid #000',
    borderRadius: '4px', cursor: 'pointer', fontSize: '13px', fontWeight: 'bold'
  };

  const dropdownStyle = {
    position: 'absolute', top: '100%', left: '0', backgroundColor: 'white',
    border: '1px solid #000', zIndex: 1000, marginTop: '2px', minWidth: '160px'
  };

  return (
    <div style={{ backgroundColor: 'white', color: 'black', minHeight: '100vh' }}>
      {/* 상단 컨트롤바 (고정) */}
      <div style={{ position: 'sticky', top: 0, backgroundColor: 'white', padding: '15px 20px', zIndex: 500, borderBottom: '2px solid black' }}>
        
        <div style={{ display: 'flex', gap: '15px', marginBottom: '15px' }}>
          <button onClick={() => navigate('/home')} style={navButtonStyle}>🏠 Home</button>
          <button onClick={() => navigate(-1)} style={navButtonStyle}>⬅️ Back</button>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
          <h2 style={{ margin: 0, fontSize: '1.2rem' }}>{songData.title} - {songData.artist}</h2>
          
          <div style={{ display: 'flex', gap: '10px' }}>
            {/* 오디오 선택 드롭다운 */}
            <div style={{ position: 'relative' }}>
              <button onClick={() => {setIsAudioMenuOpen(!isAudioMenuOpen); setIsTabMenuOpen(false);}} style={menuButtonStyle}>
                AUDIO: {audioOptions.find(o => o.key === audioMode)?.label} ▾
              </button>
              {isAudioMenuOpen && (
                <div style={dropdownStyle}>
                  {audioOptions.map(opt => (
                    <div key={opt.key} onClick={() => {setAudioMode(opt.key); setIsAudioMenuOpen(false);}} 
                         style={{ padding: '8px 12px', cursor: 'pointer', borderBottom: '1px solid #eee', fontSize: '13px' }}>
                      {opt.label}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* 악보 선택 드롭다운 */}
            <div style={{ position: 'relative' }}>
              <button onClick={() => {setIsTabMenuOpen(!isTabMenuOpen); setIsAudioMenuOpen(false);}} style={menuButtonStyle}>
                TAB: {tabOptions.find(o => o.key === tabMode)?.label} ▾
              </button>
              {isTabMenuOpen && (
                <div style={dropdownStyle}>
                  {tabOptions.map(opt => (
                    <div key={opt.key} onClick={() => {setTabMode(opt.key); setIsTabMenuOpen(false);}} 
                         style={{ padding: '8px 12px', cursor: 'pointer', borderBottom: '1px solid #eee', fontSize: '13px' }}>
                      {opt.label}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* 오디오 플레이어 */}
        <audio 
          ref={audioRef} 
          controls 
          src={currentAudioSrc} 
          onTimeUpdate={handleTimeUpdate} 
          crossOrigin="anonymous" // 외부 서버 URL 허용
          style={{ width: '100%', height: '30px' }} 
        />
      </div>

      {/* 악보 표시 영역 */}
      <div style={{ maxWidth: '1000px', margin: '40px auto', padding: '0 20px' }}>
        {chunkedBars.length > 0 ? (
          chunkedBars.map((group, idx) => (
            <div key={idx} style={{ display: 'flex', alignItems: 'center', marginBottom: '40px' }}>
              <div style={{ display: 'flex', alignItems: 'center', width: '60px', borderRight: '2px solid black' }}>
                <div style={{ display: 'flex', flexDirection: 'column', fontSize: '10px', fontWeight: 'bold', marginRight: '5px' }}>
                  <span>G</span><span>D</span><span>A</span><span>E</span>
                </div>
                <div style={{ fontSize: '18px', fontWeight: 'bold', lineHeight: '0.8' }}>4<br/>4</div>
              </div>
              <div style={{ display: 'flex', flex: 1, borderTop: '1px solid black', borderBottom: '1px solid black' }}>
                {group.map((bar) => renderSingleBar(bar, currentTime >= bar.start_time && currentTime < bar.end_time))}
                {/* 4마디가 안 채워졌을 때 빈 칸 유지 */}
                {group.length < 4 && Array(4 - group.length).fill(0).map((_, i) => (
                  <div key={`empty-${i}`} style={{ flex: 1, borderRight: '1.5px solid black' }}></div>
                ))}
              </div>
            </div>
          ))
        ) : (
          <div style={{ textAlign: 'center', marginTop: '100px', color: '#666' }}>
            악보 데이터를 불러오는 중이거나 데이터가 없습니다.
          </div>
        )}
      </div>
    </div>
  );
}

export default Player;