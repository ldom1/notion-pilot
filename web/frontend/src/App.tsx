import { Routes, Route } from 'react-router-dom'
import Landing from './pages/Landing'
import Cockpit from './pages/Cockpit'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/cockpit" element={<Cockpit />} />
    </Routes>
  )
}
