import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import waitingImg1 from '../images/기다리는사진1.png';
import waitingImg2 from '../images/기다리는사진2.png';

function Waiting() {
  const navigate = useNavigate();
  const [selectedImg, setSelectedImg] = useState(null);

  useEffect(() => {
    const images = [waitingImg1, waitingImg2];
    const randomIndex = Math.floor(Math.random() * images.length);
    setSelectedImg(images[randomIndex]);
  }, []);

  return (
    <div style={containerStyle}>
      <button onClick={() => navigate('/home')} style={homeBtnStyle}>
        🏠 Home
      </button>

      <div style={imageWrapperStyle}>
        {selectedImg && (
          <img 
            src={selectedImg} 
            alt="분석 대기 중" 
            style={mainImageStyle} 
          />
        )}
        
        <h1 style={mainTextStyle}>
          거위가 열심히 악보를 만들고 있으니<br/>
          조금만 기다려주세요!!
        </h1>
        <p style={subTextStyle}>잠시 기다리신 후 악보창에 검색해주세요!</p>
        <p style={subTextStyle}>당신을 응원합니다 믿음을 멈추지 마세요!</p>
      </div>
    </div>
  );
}

const containerStyle = {
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  height: '100vh',
  backgroundColor: '#fff',
  position: 'relative',
  overflow: 'hidden',
};

const imageWrapperStyle = {
  textAlign: 'center',
  width: '100%',
  maxWidth: '400px', 
  padding: '20px',
  boxSizing: 'border-box',
};

const mainImageStyle = {
  width: '100%',
  maxWidth: '600px', 
  height: 'auto',
  borderRadius: '30px',
  boxShadow: '0 15px 35px rgba(0,0,0,0.15)',
  marginBottom: '40px',
};

const mainTextStyle = {
  fontSize: '1.1rem', 
  fontWeight: '800',
  color: '#333',
  lineHeight: '1.4',
  wordBreak: 'keep-all', 
};

const subTextStyle = {
  fontSize: '1.1rem',
  color: '#888',
  marginTop: '15px',
};

const homeBtnStyle = {
  position: 'absolute',
  top: '20px',
  right: '20px',
  padding: '10px 15px',
  cursor: 'pointer',
  border: '1px solid #000',
  borderRadius: '5px',
  backgroundColor: '#fff',
  zIndex: 10,
};

export default Waiting;