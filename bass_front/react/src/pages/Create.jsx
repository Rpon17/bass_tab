import { useNavigate } from 'react-router-dom';

// 요청하신 대로 이미지 매칭
import guitarImg from '../images/여행가는거위.jpg'; // YouTube용
import searchImg from '../images/요원거위.png'; // 업로드용

function Create() {
  const navigate = useNavigate();

  return (
    <div style={{ padding: '40px 20px', textAlign: 'center', minHeight: '100vh', backgroundColor: '#fff' }}>
      
      {/* 상단 네비게이션 */}
      <div style={{ display: 'flex', justifyContent: 'flex-start', gap: '15px', marginBottom: '30px' }}>
        <button onClick={() => navigate('/home')} style={btnStyle}>🏠 Home</button>
        <button onClick={() => navigate(-1)} style={btnStyle}>⬅️ Back</button>
      </div>

      <h2 style={{ marginBottom: '50px', fontSize: '2.2rem', fontWeight: 'bold' }}>
        악보 제작 방식 선택
      </h2>
      
      <div style={{ display: 'flex', justifyContent: 'center', gap: '40px', flexWrap: 'wrap' }}>
        
        {/* YouTube 링크로 생성 카드 */}
        <div 
          onClick={() => navigate('/create/youtube')}
          style={cardStyle}
          onMouseOver={(e) => e.currentTarget.style.transform = 'scale(1.02)'}
          onMouseOut={(e) => e.currentTarget.style.transform = 'scale(1)'}
        >
          <div style={iconWrapperStyle}>
            <img src={guitarImg} alt="YouTube 생성" style={imageStyle} />
          </div>
          <h3 style={titleStyle}>YouTube 링크로 생성</h3>
          <p style={descStyle}>유튜브 URL을 입력하여<br/>악보를 제작합니다.</p>
        </div>

        {/* 직접 파일 업로드 카드 */}
        <div 
          onClick={() => navigate('/create/upload')}
          style={cardStyle}
          onMouseOver={(e) => e.currentTarget.style.transform = 'scale(1.02)'}
          onMouseOut={(e) => e.currentTarget.style.transform = 'scale(1)'}
        >
          <div style={iconWrapperStyle}>
            <img src={searchImg} alt="파일 업로드" style={imageStyle} />
          </div>
          <h3 style={titleStyle}>직접 파일 업로드</h3>
          <p style={descStyle}>MP3, WAV 파일을<br/>직접 올려서 제작합니다.</p>
        </div>

      </div>
    </div>
  );
}

// --- 스타일 객체 (Home 컴포넌트의 스타일 유지) ---

const btnStyle = { 
  padding: '8px 15px', 
  cursor: 'pointer', 
  border: '1px solid #000', 
  borderRadius: '8px', 
  backgroundColor: '#f5f5f5', 
  fontSize: '0.9rem',
  fontWeight: 'bold'
};

const cardStyle = {
  width: '350px',          
  padding: '50px 20px', 
  border: '2px solid #000', 
  borderRadius: '30px',
  cursor: 'pointer', 
  transition: 'transform 0.2s ease-in-out', 
  textAlign: 'center',
  backgroundColor: '#fff',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center'
};

const iconWrapperStyle = {
  width: '180px',           
  height: '180px',          
  marginBottom: '20px',
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  overflow: 'hidden'        
};

const imageStyle = {
  width: '100%',           
  height: '100%',           
  objectFit: 'contain'     
};

const titleStyle = {
  fontSize: '1.7rem',
  margin: '10px 0',
  fontWeight: 'bold'
};

const descStyle = {
  fontSize: '1.1rem',
  color: '#555',
  lineHeight: '1.5'
};

export default Create;