function MyButton({ text }) {
  return <button onClick={() => alert('클릭됨!')}>{text}</button>;
}

export default MyButton;