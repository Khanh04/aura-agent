import ChatWindow from "./ChatWindow";

export default function App() {
  return (
    <div className="app">
      <div className="topbar">
        <div className="wordmark">
          A<b>u</b>ra
        </div>
        <div className="subtitle">NGỌC HẠP THÔNG THƯ · TRA CỨU LỊCH ÂM</div>
      </div>
      <ChatWindow />
    </div>
  );
}
