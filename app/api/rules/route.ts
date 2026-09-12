/**
 * Next.js App Router API Route: /api/rules
 * GET: Retrieve all active anomaly trigger rules and custom thresholds
 * PUT: Update trigger rule thresholds (e.g. loitering time, crowd size, cooldown)
 */

import { NextRequest, NextResponse } from 'next/server';
import { getSupabaseServerClient } from '@/lib/supabaseClient';

export async function GET() {
  const supabase = getSupabaseServerClient();
  const { data, error } = await supabase
    .from('anomaly_trigger_rules')
    .select('*')
    .order('anomaly_type', { ascending: true });

  if (error) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }

  return NextResponse.json({ success: true, rules: data });
}

export async function PUT(req: NextRequest) {
  try {
    const body = await req.json();
    const { anomaly_type, enabled, default_severity, threshold_value, cooldown_period_seconds, custom_params } = body;

    if (!anomaly_type) {
      return NextResponse.json({ success: false, error: 'anomaly_type is required.' }, { status: 400 });
    }

    const supabase = getSupabaseServerClient();
    const updateData: Record<string, any> = { updated_at: new Date().toISOString() };

    if (enabled !== undefined) updateData.enabled = enabled;
    if (default_severity !== undefined) updateData.default_severity = default_severity;
    if (threshold_value !== undefined) updateData.threshold_value = threshold_value;
    if (cooldown_period_seconds !== undefined) updateData.cooldown_period_seconds = cooldown_period_seconds;
    if (custom_params !== undefined) updateData.custom_params = custom_params;

    const { data, error } = await supabase
      .from('anomaly_trigger_rules')
      .update(updateData)
      .eq('anomaly_type', anomaly_type)
      .select()
      .single();

    if (error) {
      return NextResponse.json({ success: false, error: error.message }, { status: 500 });
    }

    // Log the change in activity_logs
    await supabase.from('activity_logs').insert({
      actor: 'store_owner',
      action: 'RULE_UPDATED',
      target_entity: 'anomaly_trigger_rules',
      entity_id: anomaly_type,
      details: updateData,
    });

    return NextResponse.json({ success: true, rule: data });
  } catch (err: any) {
    return NextResponse.json({ success: false, error: err.message }, { status: 500 });
  }
}
