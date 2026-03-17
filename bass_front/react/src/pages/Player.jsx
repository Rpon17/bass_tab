import { useEffect, useState, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

function Player() {
  const location = useLocation();
  const navigate = useNavigate();
  const songData = location.state?.songData;
  
  const [tabData, setTabData] = useState(null);
  const [currentTime, setCurrentTime] = useState(0);
  
  const [audioMode, setAudioMode] = useState('original_audio_path');
  const [tabMode, setTabMode] = useState('original_tab_path');
  
  const [isAudioMenuOpen, setIsAudioMenuOpen] = useState(false);
  const [isTabMenuOpen, setIsTabMenuOpen] = useState(false);
  
  const audioRef = useRef(null);
  const currentBarRef = useRef(null);

  useEffect(() => {
    if (songData?.[tabMode]) {
      fetch(songData[tabMode])
        .then(res => res.json())
        .then(setTabData)
        .catch(err => console.error("Tab load error:", err));
    }
  }, [songData, tabMode]);

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

  if (!songData) return (
    <div style={{padding: '50px', textAlign: 'center'}}>
      <p>데이터가 없습니다.</p>
      <button onClick={() => navigate('/home')}>홈으로 가기</button>
    </div>
  );

  const chunkedBars = [];
  if (tabData && Array.isArray(tabData)) {
    for (let i = 0; i < tabData.length; i += 4) chunkedBars.push(tabData.slice(i, i + 4));
  }

  // 버튼 스타일 공통화
  const navButtonStyle = {
    background: 'none', border: 'none', cursor: 'pointer', fontSize: '1rem',
    display: 'flex', alignItems: 'center', gap: '5px', padding: '5px 10px',
    borderRadius: '5px', backgroundColor: '#f0f0f0'
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
      {/* 🧭 상단 네비게이션 및 컨트롤러 */}
      <div style={{ position: 'sticky', top: 0, backgroundColor: 'white', padding: '15px 20px', zIndex: 500, borderBottom: '2px solid black' }}>
        
        {/* 홈 & 뒤로가기 버튼 줄 */}
        <div style={{ display: 'flex', gap: '15px', marginBottom: '15px' }}>
          <button onClick={() => navigate('/home')} style={navButtonStyle}>🏠 Home</button>
          <button onClick={() => navigate(-1)} style={navButtonStyle}>⬅️ Back</button>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
          <h2 style={{ margin: 0, fontSize: '1.2rem' }}>{songData.title}</h2>
          
          <div style={{ display: 'flex', gap: '10px' }}>
            {/* Audio Dropdown */}
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

            {/* Tab Dropdown */}
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
        <audio ref={audioRef} controls src={songData[audioMode]} onTimeUpdate={handleTimeUpdate} style={{ width: '100%', height: '30px' }} />
      </div>

      {/* 악보 영역 */}
      <div style={{ maxWidth: '1000px', margin: '40px auto', padding: '0 20px' }}>
        {chunkedBars.map((group, idx) => (
          <div key={idx} style={{ display: 'flex', alignItems: 'center', marginBottom: '40px' }}>
            <div style={{ display: 'flex', alignItems: 'center', width: '60px', borderRight: '2px solid black' }}>
              <div style={{ display: 'flex', flexDirection: 'column', fontSize: '10px', fontWeight: 'bold', marginRight: '5px' }}>
                <span>G</span><span>D</span><span>A</span><span>E</span>
              </div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', lineHeight: '0.8' }}>4<br/>4</div>
            </div>
            <div style={{ display: 'flex', flex: 1, borderTop: '1px solid black', borderBottom: '1px solid black' }}>
              {group.map((bar) => renderSingleBar(bar, currentTime >= bar.start_time && currentTime < bar.end_time))}
              {group.length < 4 && Array(4 - group.length).fill(0).map((_, i) => (
                <div key={`empty-${i}`} style={{ flex: 1, borderRight: '1.5px solid black' }}></div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default Player;