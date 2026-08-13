import App from './App'
import { SignIn } from './auth'
import { useUser } from './auth-context'

export default function AuthenticatedApplication() {
  const { user } = useUser()
  return user ? <App /> : <SignIn />
}
