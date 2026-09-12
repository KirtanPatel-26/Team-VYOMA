/**
 * Supabase Client Configuration
 * Supports isomorphic browser and Node.js Next.js server environments.
 */

import { createClient, SupabaseClient } from '@supabase/supabase-js';

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://your-project.supabase.co';
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || 'your-anon-key';
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || SUPABASE_ANON_KEY;

// Browser client for frontend subscriptions and authenticated UI requests
export const supabaseBrowser: SupabaseClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// Server/admin client for Next.js API Routes and Anomaly Trigger Engine
export const getSupabaseServerClient = (): SupabaseClient => {
  return createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY, {
    auth: {
      persistSession: false,
      autoRefreshToken: false,
    },
  });
};
