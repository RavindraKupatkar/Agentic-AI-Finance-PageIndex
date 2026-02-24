import { useState, createContext, useContext } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import Sidebar from './Sidebar';

export const AppContext = createContext();
export const useAppContext = () => useContext(AppContext);

export default function AppShell() {
    const location = useLocation();
    const navigate = useNavigate();
    const isLanding = location.pathname === '/';
    const [collapsed, setCollapsed] = useState(false);
    const [activeConversationId, setActiveConversationId] = useState(null);

    const handleConversationSelect = (convId) => {
        setActiveConversationId(convId);
        if (location.pathname !== '/chat') {
            navigate('/chat');
        }
    };

    return (
        <AppContext.Provider value={{ collapsed, setCollapsed, activeConversationId, setActiveConversationId }}>
            <div className={`app-shell ${isLanding ? 'landing-layout' : ''} ${collapsed ? 'sidebar-collapsed' : ''}`}>
                {!isLanding && (
                    <Sidebar
                        onConversationSelect={handleConversationSelect}
                        activeConversationId={activeConversationId}
                    />
                )}
                <main className="app-content">
                    <Outlet />
                </main>
            </div>
        </AppContext.Provider>
    );
}
